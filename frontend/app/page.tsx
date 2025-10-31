"use client"

import { useState } from "react"
import { Header } from "@/components/header"
import { FileUploadSection } from "@/components/file-upload-section"
import { ProcessingOptionsPanel } from "@/components/processing-options-panel"
import { ProcessingStatus } from "@/components/processing-status"
import { ResultsDashboard } from "@/components/results-dashboard"
import { ReferenceCardsDisplay } from "@/components/reference-cards-display"
import { ParsedReferencesView } from "@/components/parsed-references-view"
import { ValidationControls } from "@/components/validation-controls"
import { Footer } from "@/components/footer"
import { useFileProcessing } from "@/hooks/use-api"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { parseReferencesOnly, validateBatch, getBatchInfo, ParsedBatchData, ParsedReference, ValidationMode, ValidationProgress } from "@/lib/api"
import { Sparkles, ArrowRight, FileText, CheckCircle2 } from "lucide-react"

export default function Home() {
  const [activeTab, setActiveTab] = useState("upload")
  const [workflowMode, setWorkflowMode] = useState<"classic" | "two-step">("two-step")
  
  // Classic workflow (one-step)
  const { processFile, loading, error, data, progress, reset } = useFileProcessing()
  const [processingOptions, setProcessingOptions] = useState({
    paperType: "auto",
    processReferences: true,
    validateAll: true,
  })

  // Two-step workflow state
  const [parseLoading, setParseLoading] = useState(false)
  const [parsedBatch, setParsedBatch] = useState<ParsedBatchData | null>(null)
  const [isValidating, setIsValidating] = useState(false)
  const [validationProgress, setValidationProgress] = useState<ValidationProgress | null>(null)
  const [validatedReferences, setValidatedReferences] = useState<ParsedReference[] | null>(null)

  // Classic one-step workflow handler
  const handleFileProcess = async (file: File, useStreaming?: boolean) => {
    const result = await processFile(file, {
      ...processingOptions,
      useStreaming: useStreaming ?? true
    })
    if (result) {
      setActiveTab("results")
    }
  }

  // Two-step workflow: Step 1 - Parse only
  const handleParse = async (file: File) => {
    console.log("[DEBUG] handleParse called with file:", file.name)
    try {
      setParseLoading(true)
      setParsedBatch(null)
      setValidatedReferences(null)
      
      console.log("[DEBUG] Calling parseReferencesOnly...")
      const result = await parseReferencesOnly(file, processingOptions.paperType)
      console.log("[DEBUG] Parse result:", result)
      
      if (result.success) {
        console.log("[DEBUG] Parse successful, setting batch data")
        setParsedBatch(result.data)
        setActiveTab("parsed")
      } else {
        console.error("[DEBUG] Parse failed:", result.message)
        alert(`Parse failed: ${result.message}`)
      }
    } catch (err) {
      console.error("[DEBUG] Parse error:", err)
      alert(`Parse error: ${err}`)
    } finally {
      setParseLoading(false)
    }
  }

  // Two-step workflow: Step 2 - Validate
  const handleValidate = async (mode: ValidationMode, selectedIndices?: number[], selectedApis?: string[]) => {
    if (!parsedBatch) return

    try {
      setIsValidating(true)
      setValidationProgress(null)
      
      // First, check if batch is already validated
      console.log("[DEBUG] Checking if batch already validated...")
      const batchInfo = await getBatchInfo(parsedBatch.batch_id)
      
      if (batchInfo.success && batchInfo.data?.validation_status === "validated" && batchInfo.data?.validation_result) {
        console.log("[DEBUG] Batch already validated, loading results")
        setValidatedReferences(batchInfo.data.validation_result)
        setActiveTab("validated")
        setIsValidating(false)
        return
      }

      console.log("[DEBUG] Starting validation with mode:", mode, "APIs:", selectedApis)
      setValidatedReferences(null) // Clear previous results only if not already validated
      
      const results = await validateBatch(
        parsedBatch.batch_id,
        mode,
        selectedIndices,
        (progress) => {
          console.log("[DEBUG] Validation progress:", progress)
          setValidationProgress(progress)
        },
        selectedApis
      )

      console.log("[DEBUG] Validation completed, results:", results)
      console.log("[DEBUG] Setting validatedReferences to:", results.length, "references")
      setValidatedReferences(results)
      console.log("[DEBUG] Switching to validated tab")
      setActiveTab("validated")
    } catch (err) {
      console.error("Validation failed:", err)
    } finally {
      setIsValidating(false)
    }
  }

  const handleNewFile = () => {
    reset()
    setParsedBatch(null)
    setValidatedReferences(null)
    setValidationProgress(null)
    setActiveTab("upload")
  }

  const handleViewReferences = () => {
    setActiveTab("references")
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="container mx-auto px-4 py-8 max-w-7xl">
        <div className="space-y-8">
          {/* Hero Section */}
          <div className="text-center space-y-4">
            <h1 className="text-4xl font-bold text-balance">Research Paper Reference Agent</h1>
            <p className="text-xl text-muted-foreground text-balance max-w-3xl mx-auto">
              AI-powered tool for extracting, validating, and enriching academic references from research papers. Upload
              your PDF, DOCX, or DOC files and get comprehensive reference analysis.
            </p>
            
            {/* Workflow Mode Selector */}
            <div className="flex items-center justify-center gap-4 pt-4">
              <Badge variant={workflowMode === "two-step" ? "default" : "outline"} className="text-sm py-2 px-4 cursor-pointer hover:opacity-80" onClick={() => setWorkflowMode("two-step")}>
                <Sparkles className="h-4 w-4 mr-2" />
                Two-Step Workflow (Recommended)
              </Badge>
              <Badge variant={workflowMode === "classic" ? "default" : "outline"} className="text-sm py-2 px-4 cursor-pointer hover:opacity-80" onClick={() => setWorkflowMode("classic")}>
                Classic (One-Step)
              </Badge>
            </div>
          </div>

          {/* Two-Step Workflow */}
          {workflowMode === "two-step" && (
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="upload">1. Upload & Parse</TabsTrigger>
                <TabsTrigger value="parsed" disabled={!parsedBatch}>
                  2. Review & Validate
                </TabsTrigger>
                <TabsTrigger value="validated" disabled={!validatedReferences}>
                  3. Results
                </TabsTrigger>
                <TabsTrigger value="references" disabled={!validatedReferences}>
                  4. Reference Analysis
                </TabsTrigger>
              </TabsList>

              <TabsContent value="upload" className="space-y-8">
                <Card className="border-2 border-dashed border-primary/50 bg-primary/5">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <FileText className="h-5 w-5" />
                      Step 1: Parse References
                    </CardTitle>
                    <CardDescription>
                      Upload your document to extract and parse references (no API enrichment yet)
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid lg:grid-cols-3 gap-8">
                      <div className="lg:col-span-2 space-y-6">
                        <FileUploadSection 
                          onFileProcess={handleParse} 
                          buttonText="Parse References"
                          buttonIcon={<ArrowRight className="h-4 w-4" />}
                        />
                        {parseLoading && (
                          <ProcessingStatus 
                            isVisible={parseLoading} 
                            progress={{ 
                              status: "processing", 
                              progress: 50, 
                              message: "Extracting and parsing references (fast, no API calls)..." 
                            }} 
                          />
                        )}
                      </div>

                      <div className="space-y-6">
                        <ProcessingOptionsPanel 
                          options={processingOptions} 
                          onOptionsChange={setProcessingOptions}
                          hideProcessOptions={true}
                        />
                        <Card>
                          <CardHeader>
                            <CardTitle className="text-sm">Why Two-Step?</CardTitle>
                          </CardHeader>
                          <CardContent className="text-sm text-muted-foreground space-y-2">
                            <p>✨ <strong>Review first:</strong> See what was extracted before validation</p>
                            <p>⚡ <strong>Faster initial results:</strong> Parse locally without API calls</p>
                            <p>🎯 <strong>Selective validation:</strong> Choose which references to enrich</p>
                            <p>💰 <strong>Cost efficient:</strong> Only validate what you need</p>
                          </CardContent>
                        </Card>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="parsed" className="space-y-6">
                {parsedBatch && (
                  <Card className="border-2 border-primary">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                        Step 2: Review & Validate
                      </CardTitle>
                      <CardDescription>
                        Select references to validate and enrich with external API data
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid lg:grid-cols-4 gap-6">
                        <div className="lg:col-span-3">
                          <ParsedReferencesView
                            batchId={parsedBatch.batch_id}
                            summary={parsedBatch.summary}
                            references={parsedBatch.parsed_references}
                            onValidate={(indices) => handleValidate("standard", indices.length > 0 ? indices : undefined)}
                            isValidating={isValidating}
                          />
                        </div>
                        <div>
                          <ValidationControls
                            onValidate={handleValidate}
                            isValidating={isValidating}
                            validationProgress={validationProgress || undefined}
                            selectedCount={parsedBatch.parsed_references.length}
                            needsValidationCount={parsedBatch.summary.needs_validation}
                          />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="validated" className="space-y-6">
                {/* Validation Completion Message */}
                {validationProgress && validationProgress.type === "complete" && (
                  <Card className="border-green-200 bg-green-50 dark:bg-green-950/20 dark:border-green-800">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-2 text-green-700 dark:text-green-400 mb-2">
                        <CheckCircle2 className="h-5 w-5" />
                        <span className="font-medium">Validation Complete!</span>
                      </div>
                      {validationProgress.summary && (
                        <div className="text-sm space-y-1">
                          <div>✅ Enriched: {validationProgress.summary.enriched} references</div>
                          <div>📦 From cache: {validationProgress.summary.from_cache} references</div>
                          <div>
                            💾 Cache hit rate: {validationProgress.summary.cache_stats?.hit_rate || "N/A"}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}
                
                {validatedReferences && parsedBatch && (
                  <ResultsDashboard 
                    data={{
                      file_info: parsedBatch.file_info,
                      paper_type: (parsedBatch.file_info as any).paper_type || "auto",
                      processing_time: parsedBatch.processing_time,
                      summary: {
                        total_references: validatedReferences.length,
                        successfully_processed: validatedReferences.filter(r => !r.error).length,
                        total_extracted_fields: validatedReferences.reduce((sum, r) => 
                          sum + Object.values(r.extracted_fields).filter(v => v).length, 0
                        ),
                        total_missing_fields: validatedReferences.reduce((sum, r) => 
                          sum + (r.missing_fields?.length || 0), 0
                        ),
                        enriched_count: validatedReferences.filter(r => r.api_enrichment_used).length
                      },
                      processing_results: validatedReferences.map(ref => ({
                        ...ref,
                        comparison_analysis: {},
                        flagging_analysis: {
                          missing_fields: ref.missing_fields || [],
                          replaced_fields: [],
                          conflicted_fields: [],
                          partial_fields: [],
                          data_sources_used: ref.enrichment_sources || []
                        }
                      }))
                    }} 
                    onNewFile={handleNewFile} 
                    onViewReferences={handleViewReferences} 
                  />
                )}
              </TabsContent>

              <TabsContent value="references" className="space-y-6">
                {validatedReferences && (
                  <ReferenceCardsDisplay data={validatedReferences.map(ref => ({
                    ...ref,
                    comparison_analysis: {},
                    flagging_analysis: {
                      missing_fields: ref.missing_fields || [],
                      replaced_fields: [],
                      conflicted_fields: [],
                      partial_fields: [],
                      data_sources_used: ref.enrichment_sources || []
                    }
                  }))} />
                )}
              </TabsContent>
            </Tabs>
          )}

          {/* Classic One-Step Workflow */}
          {workflowMode === "classic" && (
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
                  {loading && <ProcessingStatus isVisible={loading} progress={progress} />}
                </div>

                <div className="space-y-6">
                  <ProcessingOptionsPanel options={processingOptions} onOptionsChange={setProcessingOptions} />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="results" className="space-y-6">
              <ResultsDashboard data={data} onNewFile={handleNewFile} onViewReferences={handleViewReferences} />
            </TabsContent>

            <TabsContent value="references" className="space-y-6">
              <ReferenceCardsDisplay data={data?.processing_results || []} />
            </TabsContent>
          </Tabs>
          )}
        </div>
      </main>

      <Footer />
    </div>
  )
}
