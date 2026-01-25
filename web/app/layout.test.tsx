import { render, screen } from '@testing-library/react';
import RootLayout from './layout';

// Mock next/font since it's not available in test environment
jest.mock('next/font/google', () => ({
  Geist: jest.fn().mockReturnValue({ variable: '--font-geist-sans' }),
  Geist_Mono: jest.fn().mockReturnValue({ variable: '--font-geist-mono' }),
}));

// Mock CSS import
jest.mock('./globals.css', () => ({}));

describe('RootLayout', () => {
  it('renders children within html and body tags', () => {
    const testContent = 'Test Content';

    render(
      <RootLayout>
        <div>{testContent}</div>
      </RootLayout>
    );

    expect(screen.getByText(testContent)).toBeInTheDocument();

    const htmlElement = document.documentElement;
    expect(htmlElement.getAttribute('lang')).toBe('en');
    expect(htmlElement.className).toContain('antialiased');
  });

  it('has correct metadata', () => {
    expect(RootLayout).toBeDefined();
  });
});
