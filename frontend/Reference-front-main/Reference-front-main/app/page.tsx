"use client"

import { useState } from "react"
import { Header } from "@/components/header"
import { FileUploadSection } from "@/components/file-upload-section"
import { ProcessingOptionsPanel } from "@/components/processing-options-panel"
import { ProcessingStatus } from "@/components/processing-status"
import { ResultsDashboard } from "@/components/results-dashboard"
import { ReferenceCardsDisplay } from "@/components/reference-cards-display"
import { Footer } from "@/components/footer"
import { useFileProcessing } from "@/hooks/use-api"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export default function Home() {
  const [activeTab, setActiveTab] = useState("upload")
  const { processFile, loading, error, data, reset } = useFileProcessing()
  const [processingOptions, setProcessingOptions] = useState({
    paperType: "auto",
    processReferences: true,
    validateAll: true,
  })

  const handleFileProcess = async (file: File) => {
    const result = await processFile(file, processingOptions)
    if (result) {
      setActiveTab("results")
    }
  }

  const handleNewFile = () => {
    reset()
    setActiveTab("upload")
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="space-y-8">
          {/* Hero Section */}
          <div className="text-center space-y-4">
            <h1 className="text-4xl font-bold text-balance">Research Paper Reference Agent</h1>
            <p className="text-xl text-muted-foreground text-balance max-w-3xl mx-auto">
              AI-powered tool for extracting, validating, and enriching academic references from research papers. Upload
              your PDF, DOCX, or DOC files and get comprehensive reference analysis.
            </p>
          </div>

          {/* Main Content Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="upload">Upload & Process</TabsTrigger>
              <TabsTrigger value="results" disabled={!data}>
                Results Overview
              </TabsTrigger>
              <TabsTrigger value="references" disabled={!data}>
                Reference Analysis
              </TabsTrigger>
            </TabsList>

            <TabsContent value="upload" className="space-y-8">
              <div className="grid lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 space-y-6">
                  <FileUploadSection onFileProcess={handleFileProcess} />
                  {loading && <ProcessingStatus isVisible={loading} />}
                </div>

                <div className="space-y-6">
                  <ProcessingOptionsPanel options={processingOptions} onOptionsChange={setProcessingOptions} />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="results" className="space-y-6">
              <ResultsDashboard data={data} onNewFile={handleNewFile} />
            </TabsContent>

            <TabsContent value="references" className="space-y-6">
              <ReferenceCardsDisplay data={data?.processing_results || []} />
            </TabsContent>
          </Tabs>
        </div>
      </main>

      <Footer />
    </div>
  )
}
