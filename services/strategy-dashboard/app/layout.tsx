import type { Metadata } from 'next';
import './globals.css';
import { ThemeProvider } from '@/components/ThemeProvider';
import { LiveQuoteProvider } from '@/components/LiveQuoteProvider';
import { NavBar } from '@/components/NavBar';

export const metadata: Metadata = {
  title: 'Quantisti Strategy Dashboard',
  description: 'SPX options intelligence with ML-powered forecasts and strategy recommendations.'
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <LiveQuoteProvider>
            <NavBar />
            {children}
          </LiveQuoteProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
