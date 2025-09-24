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

const mockReferences: ReferenceData[] = [
  {
    index: 1,
    originalText:
      "Smith, J., & Johnson, M. (2023). Machine Learning Applications in Healthcare: A Comprehensive Review. Nature Medicine, 29(4), 123-135. doi:10.1038/s41591-023-02456-7",
    parserUsed: "enhanced",
    apiEnrichmentUsed: true,
    enrichmentSources: ["crossref", "openalex"],
    extractedFields: {
      familyNames: ["Smith", "Johnson"],
      givenNames: ["J", "M"],
      year: 2023,
      title: "Machine Learning Applications in Healthcare: A Comprehensive Review",
      journal: "Nature Medicine",
      doi: "10.1038/s41591-023-02456-7",
      pages: "123-135",
      publisher: "Nature Publishing Group",
      url: "https://www.nature.com/articles/s41591-023-02456-7",
      abstract:
        "Machine learning applications in healthcare have shown remarkable progress in recent years, transforming diagnostic accuracy and treatment personalization...",
    },
    qualityMetrics: {
      qualityImprovement: 25,
      finalQualityScore: 95,
    },
    missingFields: [],
    taggedOutput:
      '<reference id="ref1"><authors><author><surname>Smith</surname><given-names>J</given-names></author><author><surname>Johnson</surname><given-names>M</given-names></author></authors><year>2023</year><article-title>Machine Learning Applications in Healthcare: A Comprehensive Review</article-title><source>Nature Medicine</source><volume>29</volume><issue>4</issue><fpage>123</fpage><lpage>135</lpage><pub-id pub-id-type="doi">10.1038/s41591-023-02456-7</pub-id></reference>',
    flaggingAnalysis: {
      missingFields: [],
      replacedFields: ["doi", "publisher"],
      conflictedFields: [],
      partialFields: [],
      dataSourcesUsed: ["crossref", "openalex"],
    },
  },
  {
    index: 2,
    originalText:
      "Brown, A. et al. Deep Learning for Medical Image Analysis. IEEE Trans Med Imaging, vol. 42, pp. 567-580, 2022.",
    parserUsed: "standard",
    apiEnrichmentUsed: true,
    enrichmentSources: ["semantic_scholar"],
    extractedFields: {
      familyNames: ["Brown"],
      givenNames: ["A"],
      year: 2022,
      title: "Deep Learning for Medical Image Analysis",
      journal: "IEEE Transactions on Medical Imaging",
      doi: "",
      pages: "567-580",
      publisher: "IEEE",
      url: "",
      abstract: "",
    },
    qualityMetrics: {
      qualityImprovement: 15,
      finalQualityScore: 78,
    },
    missingFields: ["doi", "url", "abstract", "given_names"],
    taggedOutput:
      '<reference id="ref2"><authors><author><surname>Brown</surname><given-names>A</given-names></author></authors><year>2022</year><article-title>Deep Learning for Medical Image Analysis</article-title><source>IEEE Transactions on Medical Imaging</source><volume>42</volume><fpage>567</fpage><lpage>580</lpage></reference>',
    flaggingAnalysis: {
      missingFields: ["doi", "url", "abstract"],
      replacedFields: ["journal"],
      conflictedFields: [],
      partialFields: ["given_names"],
      dataSourcesUsed: ["semantic_scholar"],
    },
  },
  {
    index: 3,
    originalText: "Wilson, K. (2021). AI Ethics in Clinical Decision Making. Medical Ethics Journal.",
    parserUsed: "basic",
    apiEnrichmentUsed: false,
    enrichmentSources: [],
    extractedFields: {
      familyNames: ["Wilson"],
      givenNames: ["K"],
      year: 2021,
      title: "AI Ethics in Clinical Decision Making",
      journal: "Medical Ethics Journal",
      doi: "",
      pages: "",
      publisher: "",
      url: "",
      abstract: "",
    },
    qualityMetrics: {
      qualityImprovement: 0,
      finalQualityScore: 45,
    },
    missingFields: ["doi", "pages", "publisher", "url", "abstract"],
    taggedOutput:
      '<reference id="ref3"><authors><author><surname>Wilson</surname><given-names>K</given-names></author></authors><year>2021</year><article-title>AI Ethics in Clinical Decision Making</article-title><source>Medical Ethics Journal</source></reference>',
    flaggingAnalysis: {
      missingFields: ["doi", "pages", "publisher", "url", "abstract"],
      replacedFields: [],
      conflictedFields: [],
      partialFields: [],
      dataSourcesUsed: [],
    },
  },
]

interface ReferenceCardsDisplayProps {
  data: any[]
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

  const getStatusIcon = (qualityScore: number, hasError?: boolean) => {
    if (hasError) return <XCircle className="h-4 w-4 text-destructive" />
    if (qualityScore >= 80) return <CheckCircle className="h-4 w-4 text-success" />
    if (qualityScore >= 60) return <AlertTriangle className="h-4 w-4 text-yellow-500" />
    return <XCircle className="h-4 w-4 text-destructive" />
  }

  const getStatusColor = (qualityScore: number, hasError?: boolean) => {
    if (hasError) return "border-destructive/20 bg-destructive/5"
    if (qualityScore >= 80) return "border-success/20 bg-success/5"
    if (qualityScore >= 60) return "border-yellow-500/20 bg-yellow-500/5"
    return "border-destructive/20 bg-destructive/5"
  }

  const filteredReferences = mockReferences.filter((ref) => {
    const matchesSearch =
      ref.extractedFields.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ref.extractedFields.familyNames.some((name) => name.toLowerCase().includes(searchTerm.toLowerCase()))

    const matchesFilter =
      filterStatus === "all" ||
      (filterStatus === "high" && ref.qualityMetrics.finalQualityScore >= 80) ||
      (filterStatus === "medium" &&
        ref.qualityMetrics.finalQualityScore >= 60 &&
        ref.qualityMetrics.finalQualityScore < 80) ||
      (filterStatus === "low" && ref.qualityMetrics.finalQualityScore < 60)

    return matchesSearch && matchesFilter
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-primary" />
          Reference Analysis ({mockReferences.length} references)
        </h2>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setExpandedCards(new Set(mockReferences.map((r) => r.index)))}
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
            className={`transition-all duration-200 ${getStatusColor(reference.qualityMetrics.finalQualityScore, !!reference.error)}`}
          >
            <Collapsible open={expandedCards.has(reference.index)} onOpenChange={() => toggleCard(reference.index)}>
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(reference.qualityMetrics.finalQualityScore, !!reference.error)}
                        <Badge variant="outline" className="text-xs">
                          Ref {reference.index}
                        </Badge>
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-left truncate">
                          {reference.extractedFields.title || "Untitled Reference"}
                        </h3>
                        <p className="text-sm text-muted-foreground text-left">
                          {reference.extractedFields.familyNames.join(", ")} ({reference.extractedFields.year})
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-xs">
                        {reference.qualityMetrics.finalQualityScore}%
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
                        {reference.qualityMetrics.qualityImprovement > 0 && (
                          <Badge variant="outline" className="text-xs bg-primary/10 text-primary">
                            +{reference.qualityMetrics.qualityImprovement}% improved
                          </Badge>
                        )}
                        <Badge variant="secondary">{reference.qualityMetrics.finalQualityScore}%</Badge>
                      </div>
                    </div>
                    <Progress value={reference.qualityMetrics.finalQualityScore} className="w-full h-2" />
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
                        <p className="text-sm font-mono text-muted-foreground">{reference.originalText}</p>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(reference.originalText)}
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
                            {reference.extractedFields.familyNames
                              .map((name, i) => `${name}, ${reference.extractedFields.givenNames[i] || "?"}`)
                              .join("; ")}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">Year:</span>
                          <span className="text-xs font-medium">{reference.extractedFields.year}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">Journal:</span>
                          <span className="text-xs font-medium truncate max-w-32">
                            {reference.extractedFields.journal}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">Pages:</span>
                          <span className="text-xs font-medium">{reference.extractedFields.pages || "N/A"}</span>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">DOI:</span>
                          <div className="flex items-center gap-1">
                            <span className="text-xs font-medium truncate max-w-32">
                              {reference.extractedFields.doi || "N/A"}
                            </span>
                            {reference.extractedFields.doi && (
                              <Button variant="ghost" size="sm" className="h-4 w-4 p-0">
                                <ExternalLink className="h-3 w-3" />
                              </Button>
                            )}
                          </div>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">Publisher:</span>
                          <span className="text-xs font-medium truncate max-w-32">
                            {reference.extractedFields.publisher || "N/A"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">URL:</span>
                          <div className="flex items-center gap-1">
                            <span className="text-xs font-medium">
                              {reference.extractedFields.url ? "Available" : "N/A"}
                            </span>
                            {reference.extractedFields.url && (
                              <Button variant="ghost" size="sm" className="h-4 w-4 p-0">
                                <ExternalLink className="h-3 w-3" />
                              </Button>
                            )}
                          </div>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-muted-foreground">Abstract:</span>
                          <span className="text-xs font-medium">
                            {reference.extractedFields.abstract ? "Available" : "N/A"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Missing Fields */}
                  {reference.missingFields.length > 0 && (
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
                  {reference.apiEnrichmentUsed && (
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
                        onClick={() => copyToClipboard(reference.taggedOutput)}
                        className="text-xs"
                      >
                        <Copy className="h-3 w-3 mr-1" />
                        Copy XML
                      </Button>
                    </div>
                    <div className="p-3 bg-muted/30 rounded-lg border border-dashed max-h-32 overflow-y-auto">
                      <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap">
                        {reference.taggedOutput}
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
