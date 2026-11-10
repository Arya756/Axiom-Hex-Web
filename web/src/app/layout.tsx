import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "Axiom | Multimodal Brand Governance & Fact Verification",
  description: "Next-generation multimodal brand governance platform with deterministic-first checkers, Citation Verifier, and hash-bound approval locks.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="light">
      <body className="bg-pastel-bg text-pastel-text min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}

