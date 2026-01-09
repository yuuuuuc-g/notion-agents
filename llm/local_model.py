"""
llm/local_model.py
云端版适配器：不跑模型，只发请求
"""
import requests
from typing import Any, List, Optional
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM

class LocalNanoGPT(LLM):
    # 👇【关键】把你复制的 Hugging Face 地址填在这里
    api_url: str = "https://yuc-g-my-nanogpt-api.hf.space/generate" 

    @property
    def _llm_type(self) -> str:
        return "nano-gpt-cloud"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        # 1. 准备数据
        payload = {"prompt": prompt}
        
        try:
            # 2. 发送请求给云端 (Hugging Face)
            print(f"📡 Calling Cloud API: {self.api_url}...")
            response = requests.post(self.api_url, json=payload)
            
            # 3. 处理结果
            if response.status_code == 200:
                result = response.json()
                return result.get("reply", "")
            else:
                return f"Error: Server returned {response.status_code}"
                
        except Exception as e:
            return f"Connection Failed: {e}"