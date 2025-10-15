"use client"

import { useState } from "react"
import { BarChart3, FileText, CheckCircle, AlertTriangle, Database, Download, RefreshCw, Eye, Copy } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return "0 Bytes"
  const k = 1024
  const sizes = ["Bytes", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Number.parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

interface ProcessingStats {
  totalReferences: number
  successfullyProcessed: number
  fieldsExtracted: number
  missingFields: number
  apiEnriched: number
  qualityScore: number
  processingTime: string
}

interface FileInfo {
  filename: string
  size: string
  type: string
  paperType: string
  status: "completed" | "processing" | "error"
}

interface ResultsDashboardProps {
  data: any
  onNewFile: () => void
  onViewReferences?: () => void
}

export function ResultsDashboard({ data, onNewFile, onViewReferences }: ResultsDashboardProps) {
  const [activeTab, setActiveTab] = useState("overview")

  // Debug: Log the data structure to understand what we're receiving
  console.log("ResultsDashboard data:", data)

  if (!data) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <p className="text-muted-foreground">No processing results available</p>
        </CardContent>
      </Card>
    )
  }

  // Calculate realistic stats from the actual data
  // Handle different possible data structures
  const references = data.processing_results || data.references || []
  const totalReferences = references.length
  
  // Debug: Log references to understand the structure
  console.log("References found:", totalReferences)
  console.log("First reference:", references[0])
  const successfullyProcessed = references.filter(ref => 
    ref.status === "Verified" || ref.status === "Suspect" || !ref.error
  ).length
  const fieldsExtracted = references.reduce((total, ref) => {
    if (ref.error) return total
    const extractedFields = ref.extracted_fields || {}
    return total + Object.values(extractedFields).filter(value => 
      value && (Array.isArray(value) ? value.length > 0 : value.toString().trim() !== "")
    ).length
  }, 0)
  const missingFields = references.reduce((total, ref) => 
    total + (ref.missing_fields?.length || 0), 0
  )
  const apiEnriched = references.filter(ref => 
    ref.api_enrichment_used
  ).length
  
  // Count NER parser usage
  const nerParsed = references.filter(ref => 
    ref.parser_used && ref.parser_used.includes('NER')
  ).length
  
  // Count references with validation changes
  const withValidationChanges = references.filter(ref => 
    ref.validation_changes && ref.validation_changes.length > 0
  ).length
  
  // Count total validation changes
  const totalValidationChanges = references.reduce((total, ref) => 
    total + (ref.validation_changes?.filter(c => c.type !== 'unchanged').length || 0), 0
  )
  
  // Calculate average quality score from individual reference confidence scores
  const avgConfidence = references.length > 0 
    ? references.reduce((sum, ref) => sum + (ref.confidence || 0), 0) / references.length
    : 0
  const qualityScore = Math.round(avgConfidence * 100)

  const stats: ProcessingStats = {
    totalReferences,
    successfullyProcessed,
    fieldsExtracted,
    missingFields,
    apiEnriched,
    qualityScore,
    processingTime: data.processing_time || "Unknown",
  }

  const fileInfo: FileInfo = {
    filename: data.file_info?.filename || "Unknown",
    size: formatFileSize(data.file_info?.size || 0),
    type: data.file_info?.type?.toUpperCase() || "Unknown",
    paperType: data.paper_type || "Unknown",
    status: "completed",
  }

  const exportOptions = [
    { label: "JSON", description: "Structured data format", icon: <Database className="h-4 w-4" /> },
    { label: "CSV", description: "Spreadsheet format", icon: <FileText className="h-4 w-4" /> },
    { label: "XML", description: "Tagged output format", icon: <FileText className="h-4 w-4" /> },
  ]

  if (!data) {
    return (
      <Card className="border-dashed">
        <CardContent className="p-12 text-center">
          <div className="space-y-4">
            <div className="mx-auto w-16 h-16 bg-muted/50 rounded-full flex items-center justify-center">
              <BarChart3 className="h-8 w-8 text-muted-foreground" />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-semibold text-muted-foreground">No Results Yet</h3>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                Upload and process a research paper to see detailed reference analysis and quality metrics
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-primary" />
          <h2 className="text-xl font-semibold">Processing Results</h2>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setHasResults(false)}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Process New File
          </Button>
          <Button variant="outline" size="sm" onClick={onViewReferences}>
            <Eye className="h-4 w-4 mr-2" />
            View References
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="details">File Details</TabsTrigger>
          <TabsTrigger value="export">Export</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {/* Summary Statistics */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
              <CardContent className="p-4 text-center">
                <div className="space-y-2">
                  <FileText className="h-6 w-6 text-primary mx-auto" />
                  <div className="text-2xl font-bold text-primary">{stats.totalReferences}</div>
                  <div className="text-xs text-muted-foreground">Total References</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-success/5 to-success/10 border-success/20">
              <CardContent className="p-4 text-center">
                <div className="space-y-2">
                  <CheckCircle className="h-6 w-6 text-success mx-auto" />
                  <div className="text-2xl font-bold text-success">{stats.successfullyProcessed}</div>
                  <div className="text-xs text-muted-foreground">Successfully Processed</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-blue-500/5 to-blue-500/10 border-blue-500/20">
              <CardContent className="p-4 text-center">
                <div className="space-y-2">
                  <Database className="h-6 w-6 text-blue-500 mx-auto" />
                  <div className="text-2xl font-bold text-blue-500">{stats.fieldsExtracted}</div>
                  <div className="text-xs text-muted-foreground">Fields Extracted</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-yellow-500/5 to-yellow-500/10 border-yellow-500/20">
              <CardContent className="p-4 text-center">
                <div className="space-y-2">
                  <AlertTriangle className="h-6 w-6 text-yellow-500 mx-auto" />
                  <div className="text-2xl font-bold text-yellow-500">{stats.missingFields}</div>
                  <div className="text-xs text-muted-foreground">Missing Fields</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-purple-500/5 to-purple-500/10 border-purple-500/20">
              <CardContent className="p-4 text-center">
                <div className="space-y-2">
                  <Database className="h-6 w-6 text-purple-500 mx-auto" />
                  <div className="text-2xl font-bold text-purple-500">{stats.apiEnriched}</div>
                  <div className="text-xs text-muted-foreground">API Enriched</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-blue-500/5 to-blue-500/10 border-blue-500/20">
              <CardContent className="p-4 text-center">
                <div className="space-y-2">
                  <Database className="h-6 w-6 text-blue-500 mx-auto" />
                  <div className="text-2xl font-bold text-blue-500">{nerParsed}</div>
                  <div className="text-xs text-muted-foreground">NER Parsed</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-emerald-500/5 to-emerald-500/10 border-emerald-500/20">
              <CardContent className="p-4 text-center">
                <div className="space-y-2">
                  <CheckCircle className="h-6 w-6 text-emerald-500 mx-auto" />
                  <div className="text-2xl font-bold text-emerald-500">{totalValidationChanges}</div>
                  <div className="text-xs text-muted-foreground">Fields Improved</div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Quality Score */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-success" />
                Overall Quality Score
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Reference Quality</span>
                <Badge variant="secondary" className="bg-success/10 text-success min-w-[3rem] h-6 flex items-center justify-center">
                  {stats.qualityScore}%
                </Badge>
              </div>
              <Progress value={stats.qualityScore} className="w-full h-3" />
              <div className="grid grid-cols-3 gap-4 text-center text-sm">
                <div>
                  <div className="font-medium text-success">{stats.successfullyProcessed}</div>
                  <div className="text-muted-foreground">Complete</div>
                </div>
                <div>
                  <div className="font-medium text-yellow-500">
                    {stats.totalReferences - stats.successfullyProcessed}
                  </div>
                  <div className="text-muted-foreground">Partial</div>
                </div>
                <div>
                  <div className="font-medium text-primary">{stats.apiEnriched}</div>
                  <div className="text-muted-foreground">Enriched</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Processing Summary */}
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Processing Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Success Rate:</span>
                  <Badge variant="secondary" className="bg-success/10 text-success">
                    {stats.totalReferences > 0 ? Math.round((stats.successfullyProcessed / stats.totalReferences) * 100) : 0}%
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">API Enrichment:</span>
                  <Badge variant="secondary" className="bg-primary/10 text-primary">
                    {stats.totalReferences > 0 ? Math.round((stats.apiEnriched / stats.totalReferences) * 100) : 0}%
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">NER Parsing:</span>
                  <Badge variant="secondary" className="bg-blue-500/10 text-blue-600">
                    {stats.totalReferences > 0 ? Math.round((nerParsed / stats.totalReferences) * 100) : 0}%
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Validation Improvements:</span>
                  <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-600">
                    {totalValidationChanges} changes
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Processing Time:</span>
                  <span className="text-sm font-medium">{stats.processingTime}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Average Fields per Reference:</span>
                  <span className="text-sm font-medium">
                    {stats.successfullyProcessed > 0 ? Math.round(stats.fieldsExtracted / stats.successfullyProcessed) : 0}
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Data Sources Used</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  {(() => {
                    // Count actual data sources used
                    const sourceCounts = references.reduce((counts, ref) => {
                      if (ref.error) return counts
                      const sources = ref.enrichment_sources || []
                      sources.forEach(source => {
                        counts[source] = (counts[source] || 0) + 1
                      })
                      return counts
                    }, {})
                    
                    const sources = [
                      { name: "CrossRef", key: "crossref" },
                      { name: "OpenAlex", key: "openalex" },
                      { name: "Semantic Scholar", key: "semantic_scholar" },
                      { name: "DOAJ", key: "doaj" },
                      { name: "DOI", key: "DOI" }
                    ]
                    
                    return sources.map(source => (
                      <div key={source.key} className="flex items-center gap-2 p-2 bg-success/10 rounded-md border border-success/20">
                        <div className="w-2 h-2 bg-success rounded-full" />
                        <span className="text-xs font-medium">{source.name}</span>
                        <Badge variant="outline" className="ml-auto text-xs">
                          {sourceCounts[source.key] || 0}
                        </Badge>
                      </div>
                    ))
                  })()}
                </div>
                <p className="text-xs text-muted-foreground mt-3">
                  References were cross-validated using multiple academic databases for maximum accuracy
                </p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="details" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">File Information</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-6">
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">Filename:</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate max-w-48">{fileInfo.filename}</span>
                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">File Size:</span>
                    <span className="text-sm font-medium">{fileInfo.size}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">File Type:</span>
                    <Badge variant="secondary">{fileInfo.type}</Badge>
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">Paper Type:</span>
                    <Badge variant="outline">{fileInfo.paperType}</Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">Processing Time:</span>
                    <span className="text-sm font-medium">{stats.processingTime}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">Status:</span>
                    <Badge className="bg-success text-success-foreground">Completed</Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="export" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Export Results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Download your processed reference data in various formats for use in other applications.
              </p>

              <div className="grid gap-3">
                {exportOptions.map((option) => (
                  <div
                    key={option.label}
                    className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-muted-foreground">{option.icon}</div>
                      <div>
                        <div className="font-medium">{option.label}</div>
                        <div className="text-xs text-muted-foreground">{option.description}</div>
                      </div>
                    </div>
                    <Button variant="outline" size="sm">
                      <Download className="h-4 w-4 mr-2" />
                      Download
                    </Button>
                  </div>
                ))}
              </div>

              <Separator />

              <div className="space-y-3">
                <h4 className="font-medium">Export Options</h4>
                <div className="text-sm text-muted-foreground space-y-1">
                  <p>
                    • <strong>JSON:</strong> Complete structured data with all extracted fields and metadata
                  </p>
                  <p>
                    • <strong>CSV:</strong> Tabular format suitable for spreadsheet applications
                  </p>
                  <p>
                    • <strong>XML:</strong> Tagged output format with reference markup
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
