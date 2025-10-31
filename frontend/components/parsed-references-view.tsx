"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ParsedReference, ParseSummary } from "@/lib/api"
import { ChevronDown, ChevronUp, CheckCircle2, XCircle, AlertCircle, FileText } from "lucide-react"

interface ParsedReferencesViewProps {
  batchId: string
  summary: ParseSummary
  references: ParsedReference[]
  onValidate?: (selectedIndices: number[]) => void
  isValidating?: boolean
}

export function ParsedReferencesView({
  batchId,
  summary,
  references,
  onValidate,
  isValidating = false
}: ParsedReferencesViewProps) {
  const [selectedReferences, setSelectedReferences] = useState<Set<number>>(new Set())
  const [expandedRefs, setExpandedRefs] = useState<Set<number>>(new Set())

  const toggleReference = (index: number) => {
    const newSet = new Set(selectedReferences)
    if (newSet.has(index)) {
      newSet.delete(index)
    } else {
      newSet.add(index)
    }
    setSelectedReferences(newSet)
  }

  const toggleExpanded = (index: number) => {
    const newSet = new Set(expandedRefs)
    if (newSet.has(index)) {
      newSet.delete(index)
    } else {
      newSet.add(index)
    }
    setExpandedRefs(newSet)
  }

  const selectAll = () => {
    setSelectedReferences(new Set(references.map((_, i) => i)))
  }

  const selectNone = () => {
    setSelectedReferences(new Set())
  }

  const selectNeedingValidation = () => {
    const indices = references
      .map((ref, i) => ({ ref, i }))
      .filter(({ ref }) => ref.missing_fields && ref.missing_fields.length > 0)
      .map(({ i }) => i)
    setSelectedReferences(new Set(indices))
  }

  const getQualityColor = (score: number) => {
    if (score >= 0.8) return "text-green-600"
    if (score >= 0.5) return "text-yellow-600"
    return "text-red-600"
  }

  const getQualityLabel = (score: number) => {
    if (score >= 0.8) return "Good"
    if (score >= 0.5) return "Fair"
    return "Poor"
  }

  return (
    <div className="space-y-4">
      {/* Summary Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Parsed References Summary
          </CardTitle>
          <CardDescription>
            Batch ID: <code className="text-xs bg-muted px-1 py-0.5 rounded">{batchId}</code>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{summary.total_references}</div>
              <div className="text-sm text-muted-foreground">Total</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{summary.successfully_parsed}</div>
              <div className="text-sm text-muted-foreground">Parsed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600">{summary.needs_validation}</div>
              <div className="text-sm text-muted-foreground">Need Validation</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">{summary.total_missing_fields}</div>
              <div className="text-sm text-muted-foreground">Missing Fields</div>
            </div>
          </div>

          {/* Selection Controls */}
          <div className="mt-4 pt-4 border-t flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={selectAll}>
              Select All
            </Button>
            <Button variant="outline" size="sm" onClick={selectNone}>
              Select None
            </Button>
            <Button variant="outline" size="sm" onClick={selectNeedingValidation}>
              Select Needing Validation ({summary.needs_validation})
            </Button>
            <div className="ml-auto text-sm text-muted-foreground">
              {selectedReferences.size} selected
            </div>
          </div>
        </CardContent>
      </Card>

      {/* References List */}
      <div className="space-y-2">
        {references.map((ref, index) => {
          const isExpanded = expandedRefs.has(index)
          const isSelected = selectedReferences.has(index)
          const quality = ref.quality_metrics?.initial_quality_score || 0
          const hasError = !!ref.error
          const needsValidation = ref.missing_fields && ref.missing_fields.length > 0

          return (
            <Card
              key={index}
              className={`transition-colors ${
                isSelected ? "border-primary border-2" : ""
              } ${hasError ? "border-red-300" : ""}`}
            >
              <Collapsible open={isExpanded} onOpenChange={() => toggleExpanded(index)}>
                <div className="flex items-start gap-3 p-4">
                  {/* Checkbox */}
                  <Checkbox
                    checked={isSelected}
                    onCheckedChange={() => toggleReference(index)}
                    className="mt-1"
                  />

                  {/* Main Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-muted-foreground">
                          #{index + 1}
                        </span>
                        {hasError && (
                          <Badge variant="destructive" className="flex items-center gap-1">
                            <XCircle className="h-3 w-3" />
                            Error
                          </Badge>
                        )}
                        {!hasError && needsValidation && (
                          <Badge variant="secondary" className="flex items-center gap-1">
                            <AlertCircle className="h-3 w-3" />
                            Needs Validation
                          </Badge>
                        )}
                        {!hasError && !needsValidation && (
                          <Badge variant="default" className="flex items-center gap-1 bg-green-600">
                            <CheckCircle2 className="h-3 w-3" />
                            Complete
                          </Badge>
                        )}
                        <Badge variant="outline">{ref.parser_used}</Badge>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium ${getQualityColor(quality)}`}>
                          {getQualityLabel(quality)} ({(quality * 100).toFixed(0)}%)
                        </span>
                        <CollapsibleTrigger asChild>
                          <Button variant="ghost" size="sm">
                            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          </Button>
                        </CollapsibleTrigger>
                      </div>
                    </div>

                    {/* Reference Text */}
                    <p className="text-sm text-foreground line-clamp-2 mb-2">
                      {ref.original_text}
                    </p>

                    {/* Quick Info */}
                    {!hasError && (
                      <div className="flex flex-wrap gap-2 text-xs">
                        {ref.extracted_fields.title && (
                          <Badge variant="secondary" className="font-normal">
                            ✓ Title
                          </Badge>
                        )}
                        {(ref.extracted_fields.full_names || ref.extracted_fields.family_names)?.length > 0 && (
                          <Badge variant="secondary" className="font-normal">
                            ✓ Authors ({(ref.extracted_fields.full_names || ref.extracted_fields.family_names).length})
                          </Badge>
                        )}
                        {ref.extracted_fields.year && (
                          <Badge variant="secondary" className="font-normal">
                            ✓ Year
                          </Badge>
                        )}
                        {ref.extracted_fields.journal && (
                          <Badge variant="secondary" className="font-normal">
                            ✓ Journal
                          </Badge>
                        )}
                        {ref.extracted_fields.doi && (
                          <Badge variant="secondary" className="font-normal">
                            ✓ DOI
                          </Badge>
                        )}
                        {ref.missing_fields && ref.missing_fields.length > 0 && (
                          <Badge variant="outline" className="font-normal text-orange-600">
                            ⚠ {ref.missing_fields.length} missing
                          </Badge>
                        )}
                      </div>
                    )}

                    {hasError && (
                      <div className="text-sm text-red-600">
                        Error: {ref.error}
                      </div>
                    )}
                  </div>
                </div>

                {/* Expanded Details */}
                <CollapsibleContent>
                  <div className="px-4 pb-4 border-t pt-4 space-y-3">
                    {/* Extracted Fields */}
                    <div>
                      <h4 className="text-sm font-medium mb-2">Extracted Fields</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                        {ref.extracted_fields.title && (
                          <div>
                            <span className="text-muted-foreground">Title:</span>{" "}
                            <span className="font-medium">{ref.extracted_fields.title}</span>
                          </div>
                        )}
                        {(ref.extracted_fields.full_names || ref.extracted_fields.family_names) && 
                         (ref.extracted_fields.full_names || ref.extracted_fields.family_names).length > 0 && (
                          <div>
                            <span className="text-muted-foreground">Authors:</span>{" "}
                            <span className="font-medium">
                              {ref.extracted_fields.full_names && ref.extracted_fields.full_names.length > 0
                                ? ref.extracted_fields.full_names.join(", ")
                                : ref.extracted_fields.family_names && ref.extracted_fields.given_names
                                ? ref.extracted_fields.family_names.map((family: string, i: number) => {
                                    const given = ref.extracted_fields.given_names?.[i] || ""
                                    return given ? `${given} ${family}` : family
                                  }).join(", ")
                                : ref.extracted_fields.family_names?.join(", ") || "N/A"
                              }
                            </span>
                          </div>
                        )}
                        {ref.extracted_fields.year && (
                          <div>
                            <span className="text-muted-foreground">Year:</span>{" "}
                            <span className="font-medium">{ref.extracted_fields.year}</span>
                          </div>
                        )}
                        {ref.extracted_fields.journal && (
                          <div>
                            <span className="text-muted-foreground">Journal:</span>{" "}
                            <span className="font-medium">{ref.extracted_fields.journal}</span>
                          </div>
                        )}
                        {ref.extracted_fields.doi && (
                          <div>
                            <span className="text-muted-foreground">DOI:</span>{" "}
                            <span className="font-medium">{ref.extracted_fields.doi}</span>
                          </div>
                        )}
                        {ref.extracted_fields.pages && (
                          <div>
                            <span className="text-muted-foreground">Pages:</span>{" "}
                            <span className="font-medium">{ref.extracted_fields.pages}</span>
                          </div>
                        )}
                        {ref.extracted_fields.publisher && (
                          <div>
                            <span className="text-muted-foreground">Publisher:</span>{" "}
                            <span className="font-medium">{ref.extracted_fields.publisher}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Missing Fields */}
                    {ref.missing_fields && ref.missing_fields.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium mb-2 text-orange-600">
                          Missing Fields ({ref.missing_fields.length})
                        </h4>
                        <div className="flex flex-wrap gap-1">
                          {ref.missing_fields.map((field) => (
                            <Badge key={field} variant="outline" className="text-orange-600">
                              {field}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Original Text */}
                    <div>
                      <h4 className="text-sm font-medium mb-2">Original Text</h4>
                      <p className="text-sm text-muted-foreground bg-muted p-2 rounded">
                        {ref.original_text}
                      </p>
                    </div>
                  </div>
                </CollapsibleContent>
              </Collapsible>
            </Card>
          )
        })}
      </div>

      {/* Validate Button at Bottom */}
      {onValidate && (
        <div className="sticky bottom-4 bg-background/80 backdrop-blur-sm border rounded-lg p-4 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Ready to validate?</div>
              <div className="text-sm text-muted-foreground">
                {selectedReferences.size > 0
                  ? `${selectedReferences.size} reference${selectedReferences.size !== 1 ? "s" : ""} selected`
                  : "Select references to validate"}
              </div>
            </div>
            <Button
              onClick={() => onValidate(Array.from(selectedReferences))}
              disabled={isValidating || selectedReferences.size === 0}
              size="lg"
            >
              {isValidating ? "Validating..." : `Validate ${selectedReferences.size > 0 ? `(${selectedReferences.size})` : ""}`}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}


