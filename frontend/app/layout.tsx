import type React from "react"
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
})

import { AuthProvider } from "@/context/auth-context"

export const metadata: Metadata = {
  title: "Research Paper Reference Agent",
  description: "AI-powered tool for extracting and enriching academic references from research papers",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${inter.variable} antialiased`}>
      <body className="font-sans">
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  )
}
