"use client"

import React, { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ValidationMode, ValidationProgress } from "@/lib/api"
import { Zap, BarChart3, Microscope, CheckCircle2, Loader2, TrendingUp } from "lucide-react"

interface ValidationControlsProps {
  onValidate: (mode: ValidationMode, selectedIndices?: number[]) => void
  isValidating: boolean
  validationProgress?: ValidationProgress
  selectedCount?: number
  needsValidationCount?: number
}

export function ValidationControls({
  onValidate,
  isValidating,
  validationProgress,
  selectedCount = 0,
  needsValidationCount = 0
}: ValidationControlsProps) {
  const [mode, setMode] = useState<ValidationMode>("standard")

  const validationModes = [
    {
      value: "quick" as ValidationMode,
      label: "Quick",
      description: "Only validate references missing DOI",
      icon: Zap,
      color: "text-blue-600"
    },
    {
      value: "standard" as ValidationMode,
      label: "Standard",
      description: "Validate references that need enrichment",
      icon: BarChart3,
      color: "text-green-600"
    },
    {
      value: "thorough" as ValidationMode,
      label: "Thorough",
      description: "Validate all references with full enrichment",
      icon: Microscope,
      color: "text-purple-600"
    }
  ]

  const selectedMode = validationModes.find((m) => m.value === mode) || validationModes[1]

  return (
    <Card className="sticky top-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          Validation Controls
        </CardTitle>
        <CardDescription>
          Choose validation mode and enrich references with API data
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Mode Selection */}
        {!isValidating && (
          <div className="space-y-2">
            <label className="text-sm font-medium">Validation Mode</label>
            <div className="grid grid-cols-1 gap-2">
              {validationModes.map((modeOption) => {
                const Icon = modeOption.icon
                const isSelected = mode === modeOption.value

                return (
                  <button
                    key={modeOption.value}
                    onClick={() => setMode(modeOption.value)}
                    className={`p-3 rounded-lg border-2 transition-all text-left ${
                      isSelected
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <Icon className={`h-5 w-5 mt-0.5 ${modeOption.color}`} />
                      <div className="flex-1">
                        <div className="font-medium">{modeOption.label}</div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {modeOption.description}
                        </div>
                      </div>
                      {isSelected && (
                        <CheckCircle2 className="h-5 w-5 text-primary" />
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Progress Display */}
        {isValidating && validationProgress && (
          <div className="space-y-3">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">Validating References</span>
                <span className="text-muted-foreground">
                  {validationProgress.current || 0} / {validationProgress.total || 0}
                </span>
              </div>
              <Progress value={validationProgress.progress || 0} className="h-2" />
              <p className="text-xs text-muted-foreground">{validationProgress.message}</p>
            </div>

            {/* Live Stats */}
            {validationProgress.type === "result" && validationProgress.data && (
              <div className="p-3 rounded-lg bg-primary/5 border border-primary/20">
                <div className="text-sm font-medium text-primary mb-1">Latest Update</div>
                <div className="text-xs text-muted-foreground">
                  Reference #{(validationProgress.index || 0) + 1}:{" "}
                  {validationProgress.data.api_enrichment_used
                    ? "✅ Enriched"
                    : validationProgress.data.from_cache
                    ? "📦 From cache"
                    : "⚪ Unchanged"}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Summary Stats */}
        {!isValidating && (
          <div className="grid grid-cols-2 gap-3">
            <div className="text-center p-3 rounded-lg bg-blue-50 dark:bg-blue-950/20">
              <div className="text-lg font-bold text-blue-600">{selectedCount}</div>
              <div className="text-xs text-muted-foreground">Selected</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-orange-50 dark:bg-orange-950/20">
              <div className="text-lg font-bold text-orange-600">{needsValidationCount}</div>
              <div className="text-xs text-muted-foreground">Need Validation</div>
            </div>
          </div>
        )}

        {/* Action Button */}
        <Button
          onClick={() => onValidate(mode)}
          disabled={isValidating || selectedCount === 0}
          className="w-full"
          size="lg"
        >
          {isValidating ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Validating...
            </>
          ) : (
            <>
              {React.createElement(selectedMode.icon, { className: "mr-2 h-4 w-4" })}
              Validate {selectedCount > 0 ? `${selectedCount} Reference${selectedCount !== 1 ? "s" : ""}` : ""}
            </>
          )}
        </Button>

        {/* Mode Info */}
        {!isValidating && (
          <div className="text-xs text-muted-foreground p-3 rounded-lg bg-muted">
            <div className="font-medium mb-1">About {selectedMode.label} Mode</div>
            <p>{selectedMode.description}</p>
            <div className="mt-2 flex items-center gap-1">
              <Badge variant="outline" className="text-xs">
                {mode === "quick" ? "~30s" : mode === "standard" ? "~2-3min" : "~5-10min"}
              </Badge>
              <span className="text-muted-foreground">estimated time</span>
            </div>
          </div>
        )}

        {/* Completion Message */}
        {validationProgress && validationProgress.type === "complete" && (
          <div className="p-4 rounded-lg bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800">
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
          </div>
        )}
      </CardContent>
    </Card>
  )
}

