"use client"

import { useState } from "react"
import {
  ChevronDown,
  ChevronUp,
  Copy,
  ExternalLink,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Database,
  Star,
  BookOpen,
  Eye,
  EyeOff,
} from "lucide-react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface ReferenceData {
  index: number
  originalText: string
  parserUsed: string
  apiEnrichmentUsed: boolean
  enrichmentSources: string[]
  extractedFields: {
    familyNames: string[]
    givenNames: string[]
    year: number
    title: string
    journal: string
    doi: string
    pages: string
    publisher: string
    url: string
    abstract: string
  }
  qualityMetrics: {
    qualityImprovement: number
    finalQualityScore: number
  }
  missingFields: string[]
  taggedOutput: string
  flaggingAnalysis: {
    missingFields: string[]
    replacedFields: string[]
    conflictedFields: string[]
    partialFields: string[]
    dataSourcesUsed: string[]
  }
  error?: string
}


interface ReferenceCardsDisplayProps {
  data: any[]
}

// Helper function to normalize API response to expected interface format
function normalizeReference(ref: any): ReferenceData {
  return {
    index: ref.index || 0,
    originalText: ref.originalText || ref.original_text || "",
    parserUsed: ref.parserUsed || ref.parser_used || "unknown",
    apiEnrichmentUsed: ref.apiEnrichmentUsed || ref.api_enrichment_used || false,
    enrichmentSources: ref.enrichmentSources || ref.enrichment_sources || [],
    extractedFields: {
      familyNames: ref.extractedFields?.familyNames || ref.extracted_fields?.family_names || [],
      givenNames: ref.extractedFields?.givenNames || ref.extracted_fields?.given_names || [],
      year: ref.extractedFields?.year || ref.extracted_fields?.year || 0,
      title: ref.extractedFields?.title || ref.extracted_fields?.title || "",
      journal: ref.extractedFields?.journal || ref.extracted_fields?.journal || "",
      doi: ref.extractedFields?.doi || ref.extracted_fields?.doi || "",
      pages: ref.extractedFields?.pages || ref.extracted_fields?.pages || "",
      publisher: ref.extractedFields?.publisher || ref.extracted_fields?.publisher || "",
      url: ref.extractedFields?.url || ref.extracted_fields?.url || "",
      abstract: ref.extractedFields?.abstract || ref.extracted_fields?.abstract || "",
    },
    qualityMetrics: {
      qualityImprovement: ref.qualityMetrics?.qualityImprovement || ref.quality_metrics?.quality_improvement || 0,
      finalQualityScore: ref.qualityMetrics?.finalQualityScore || ref.quality_metrics?.final_quality_score || 0,
    },
    missingFields: ref.missingFields || ref.missing_fields || [],
    taggedOutput: ref.taggedOutput || ref.tagged_output || "",
    flaggingAnalysis: ref.flaggingAnalysis || ref.flagging_analysis || {},
    error: ref.error
  }
}

export function ReferenceCardsDisplay({ data }: ReferenceCardsDisplayProps) {
  const [expandedCards, setExpandedCards] = useState<Set<number>>(new Set())
  const [searchTerm, setSearchTerm] = useState("")
  const [filterStatus, setFilterStatus] = useState("all")
  const [showOriginalText, setShowOriginalText] = useState<Set<number>>(new Set())


  if (!data || data.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <p className="text-muted-foreground">No reference data available</p>
        </CardContent>
      </Card>
    )
  }

  // Normalize and filter references
  const normalizedReferences = data.map(ref => normalizeReference(ref))
  
  const validReferences = normalizedReferences.filter((ref) => {
    return ref && 
      typeof ref === 'object' && 
      ref.index !== undefined &&
      (ref.originalText || ref.extractedFields || ref.error)
  })

  if (validReferences.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <p className="text-muted-foreground">No valid reference data available</p>
        </CardContent>
      </Card>
    )
  }

  const toggleCard = (index: number) => {
    const newExpanded = new Set(expandedCards)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedCards(newExpanded)
  }

  const toggleOriginalText = (index: number) => {
    const newShowOriginal = new Set(showOriginalText)
    if (newShowOriginal.has(index)) {
      newShowOriginal.delete(index)
    } else {
      newShowOriginal.add(index)
    }
    setShowOriginalText(newShowOriginal)
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const getStatusIcon = (qualityScore: number | undefined, hasError?: boolean) => {
    if (hasError || qualityScore === undefined) return <XCircle className="h-4 w-4 text-destructive" />
    const percentageScore = Math.round((qualityScore || 0) * 100)
    if (percentageScore >= 80) return <CheckCircle className="h-4 w-4 text-success" />
    if (percentageScore >= 60) return <AlertTriangle className="h-4 w-4 text-yellow-500" />
    return <XCircle className="h-4 w-4 text-destructive" />
  }

  const getStatusColor = (qualityScore: number | undefined, hasError?: boolean) => {
    if (hasError || qualityScore === undefined) return "border-destructive/20 bg-destructive/5"
    const percentageScore = Math.round((qualityScore || 0) * 100)
    if (percentageScore >= 80) return "border-success/20 bg-success/5"
    if (percentageScore >= 60) return "border-yellow-500/20 bg-yellow-500/5"
    return "border-destructive/20 bg-destructive/5"
  }

  const filteredReferences = validReferences.filter((ref) => {
    // More robust search that includes original text
    const matchesSearch = searchTerm === "" || 
      ref.extractedFields?.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ref.extractedFields?.familyNames?.some((name) => name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      ref.originalText?.toLowerCase().includes(searchTerm.toLowerCase())

    const matchesFilter =
      filterStatus === "all" ||
      (filterStatus === "high" && !ref.error && (ref.qualityMetrics?.finalQualityScore || 0) >= 0.8) ||
      (filterStatus === "medium" &&
        !ref.error &&
        (ref.qualityMetrics?.finalQualityScore || 0) >= 0.6 &&
        (ref.qualityMetrics?.finalQualityScore || 0) < 0.8) ||
      (filterStatus === "low" && !ref.error && (ref.qualityMetrics?.finalQualityScore || 0) < 0.6)

    return matchesSearch && matchesFilter
  })


  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-primary" />
          Reference Analysis ({validReferences.length} references)
        </h2>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setExpandedCards(new Set(validReferences.map((r) => r.index)))}
          >
            Expand All
          </Button>
          <Button variant="outline" size="sm" onClick={() => setExpandedCards(new Set())}>
            Collapse All
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <Input
            placeholder="Search references by title or author..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full"
          />
        </div>
        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Filter by quality" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All References</SelectItem>
            <SelectItem value="high">High Quality (80%+)</SelectItem>
            <SelectItem value="medium">Medium Quality (60-79%)</SelectItem>
            <SelectItem value="low">Low Quality (&lt;60%)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Reference Cards */}
      <div className="space-y-4">
        {filteredReferences.map((reference) => (
          <Card
            key={reference.index}
            className={`transition-all duration-200 ${getStatusColor(reference.qualityMetrics?.finalQualityScore, !!reference.error)}`}
          >
            <Collapsible open={expandedCards.has(reference.index)} onOpenChange={() => toggleCard(reference.index)}>
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(reference.qualityMetrics?.finalQualityScore, !!reference.error)}
                        <Badge variant="outline" className="text-xs">
                          Ref {reference.index}
                        </Badge>
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-left truncate">
                          {reference.error 
                            ? reference.originalText?.substring(0, 100) + (reference.originalText?.length > 100 ? "..." : "") || "Reference with parsing error"
                            : reference.extractedFields?.title || "Untitled Reference"
                          }
                        </h3>
                        <p className="text-sm text-muted-foreground text-left">
                          {reference.error 
                            ? "Parsing Error"
                            : `${reference.extractedFields?.familyNames?.join(", ") || "Unknown"} (${reference.extractedFields?.year || "Unknown"})`
                          }
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-xs min-w-[3rem] h-6 flex items-center justify-center">
                        {reference.error ? "Error" : `${Math.round((reference.qualityMetrics?.finalQualityScore || 0) * 100)}%`}
                      </Badge>
                      {expandedCards.has(reference.index) ? (
                        <ChevronUp className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      )}
                    </div>
                  </div>
                </CardHeader>
              </CollapsibleTrigger>

              <CollapsibleContent>
                <CardContent className="pt-0 space-y-6">
                  {/* Quality Metrics */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Quality Score</span>
                      <div className="flex items-center gap-2">
                        {(reference.qualityMetrics?.qualityImprovement || 0) > 0 && (
                          <Badge variant="outline" className="text-xs bg-primary/10 text-primary min-w-fit h-6 flex items-center justify-center">
                            +{Math.round((reference.qualityMetrics?.qualityImprovement || 0) * 100)}% improved
                          </Badge>
                        )}
                        <Badge variant="secondary" className="min-w-[3rem] h-6 flex items-center justify-center">{Math.round((reference.qualityMetrics?.finalQualityScore || 0) * 100)}%</Badge>
                      </div>
                    </div>
                    <Progress value={(reference.qualityMetrics?.finalQualityScore || 0) * 100} className="w-full h-2" />
                  </div>

                  <Separator />

                  {/* Original Text Toggle */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Original Reference</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleOriginalText(reference.index)}
                        className="text-xs"
                      >
                        {showOriginalText.has(reference.index) ? (
                          <>
                            <EyeOff className="h-3 w-3 mr-1" />
                            Hide
                          </>
                        ) : (
                          <>
                            <Eye className="h-3 w-3 mr-1" />
                            Show
                          </>
                        )}
                      </Button>
                    </div>
                    {showOriginalText.has(reference.index) && (
                      <div className="p-3 bg-muted/30 rounded-lg border border-dashed">
                        <p className="text-sm font-mono text-muted-foreground">{reference.originalText || "No original text available"}</p>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(reference.originalText || "")}
                          className="mt-2 text-xs"
                        >
                          <Copy className="h-3 w-3 mr-1" />
                          Copy
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* Extracted Fields */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-medium flex items-center gap-2">
                      <Database className="h-4 w-4" />
                      Extracted Fields
                    </h4>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">Authors:</span>
                          <span className="text-xs font-medium">
                            {reference.extractedFields?.familyNames?.length > 0 
                              ? reference.extractedFields.familyNames
                                  .map((name, i) => `${name}, ${reference.extractedFields?.givenNames?.[i] || "?"}`)
                                  .join("; ")
                              : "N/A"
                            }
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">Year:</span>
                          <span className="text-xs font-medium">{reference.extractedFields?.year || "N/A"}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">Journal:</span>
                          <span className="text-xs font-medium truncate max-w-32">
                            {reference.extractedFields?.journal || "N/A"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">Pages:</span>
                          <span className="text-xs font-medium">{reference.extractedFields?.pages || "N/A"}</span>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">DOI:</span>
                          <div className="flex items-center gap-1">
                            <span className="text-xs font-medium truncate max-w-32">
                              {reference.extractedFields?.doi || "N/A"}
                            </span>
                            {reference.extractedFields?.doi && (
                              <Button variant="ghost" size="sm" className="h-4 w-4 p-0">
                                <ExternalLink className="h-3 w-3" />
                              </Button>
                            )}
                          </div>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">Publisher:</span>
                          <span className="text-xs font-medium truncate max-w-32">
                            {reference.extractedFields?.publisher || "N/A"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">URL:</span>
                          <div className="flex items-center gap-1">
                            <span className="text-xs font-medium">
                              {reference.extractedFields?.url ? "Available" : "N/A"}
                            </span>
                            {reference.extractedFields?.url && (
                              <Button variant="ghost" size="sm" className="h-4 w-4 p-0">
                                <ExternalLink className="h-3 w-3" />
                              </Button>
                            )}
                          </div>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">Abstract:</span>
                          <span className="text-xs font-medium">
                            {reference.extractedFields?.abstract ? "Available" : "N/A"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Missing Fields */}
                  {reference.missingFields?.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-medium text-yellow-600">Missing Fields</h4>
                      <div className="flex flex-wrap gap-1">
                        {reference.missingFields.map((field) => (
                          <Badge key={field} variant="outline" className="text-xs border-yellow-500/20 text-yellow-600">
                            {field}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* API Enrichment Info */}
                  {reference.apiEnrichmentUsed && reference.enrichmentSources?.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-medium flex items-center gap-2">
                        <Star className="h-4 w-4 text-primary" />
                        API Enrichment
                      </h4>
                      <div className="flex flex-wrap gap-1">
                        {reference.enrichmentSources.map((source) => (
                          <Badge key={source} variant="secondary" className="text-xs bg-primary/10 text-primary">
                            {source}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tagged Output */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium">Tagged Output (XML)</h4>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyToClipboard(reference.taggedOutput || "")}
                        className="text-xs"
                      >
                        <Copy className="h-3 w-3 mr-1" />
                        Copy XML
                      </Button>
                    </div>
                    <div className="p-3 bg-muted/30 rounded-lg border border-dashed max-h-32 overflow-y-auto">
                      <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap">
                        {reference.taggedOutput || "No tagged output available"}
                      </pre>
                    </div>
                  </div>
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        ))}
      </div>

      {filteredReferences.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="p-8 text-center">
            <div className="space-y-2">
              <BookOpen className="h-8 w-8 text-muted-foreground mx-auto" />
              <h3 className="font-medium text-muted-foreground">No references found</h3>
              <p className="text-sm text-muted-foreground">Try adjusting your search terms or filter criteria</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
