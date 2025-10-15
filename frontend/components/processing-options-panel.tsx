"use client"

import { useState } from "react"
import { Settings, HelpCircle, Database, Shield, Zap, Clock } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"

interface ProcessingOptions {
  paperType: string
  processReferences: boolean
  validateAll: boolean
}

interface ProcessingOptionsPanelProps {
  options: ProcessingOptions
  onOptionsChange: (options: ProcessingOptions) => void
  hideProcessOptions?: boolean
}

export function ProcessingOptionsPanel({ options, onOptionsChange, hideProcessOptions = false }: ProcessingOptionsPanelProps) {
  const { paperType, processReferences, validateAll } = options

  const paperTypes = [
    {
      value: "auto",
      label: "Auto-detect",
      description: "Automatically detect paper format",
      icon: <Zap className="h-4 w-4" />,
      recommended: true,
    },
    {
      value: "ACL",
      label: "ACL",
      description: "Association for Computational Linguistics",
      icon: <Database className="h-4 w-4" />,
    },
    {
      value: "IEEE",
      label: "IEEE",
      description: "Institute of Electrical and Electronics Engineers",
      icon: <Database className="h-4 w-4" />,
    },
    {
      value: "ACM",
      label: "ACM",
      description: "Association for Computing Machinery",
      icon: <Database className="h-4 w-4" />,
    },
    {
      value: "Elsevier",
      label: "Elsevier",
      description: "Elsevier journals",
      icon: <Database className="h-4 w-4" />,
    },
    {
      value: "Springer",
      label: "Springer",
      description: "Springer publications",
      icon: <Database className="h-4 w-4" />,
    },
    {
      value: "Generic",
      label: "Generic",
      description: "Generic academic format",
      icon: <Database className="h-4 w-4" />,
    },
  ]

  const selectedPaperType = paperTypes.find((type) => type.value === paperType)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-5 w-5" />
          Processing Options
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Paper Type Selection */}
        <div className="space-y-3">
          <Label htmlFor="paper-type" className="flex items-center gap-2 text-sm font-medium">
            Paper Type
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger>
                  <HelpCircle className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent side="right" className="max-w-xs">
                  <p>Select the paper format for optimized reference extraction. Auto-detect works for most papers.</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </Label>

          <Select value={paperType} onValueChange={(value) => onOptionsChange({ ...options, paperType: value })}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select paper type" />
            </SelectTrigger>
            <SelectContent>
              {paperTypes.map((type) => (
                <SelectItem key={type.value} value={type.value}>
                  <div className="flex items-center gap-3 py-1">
                    <div className="text-muted-foreground">{type.icon}</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{type.label}</span>
                        {type.recommended && (
                          <Badge variant="secondary" className="text-xs bg-primary/10 text-primary">
                            Recommended
                          </Badge>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">{type.description}</div>
                    </div>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Selected Type Info */}
          {selectedPaperType && (
            <div className="p-3 bg-muted/30 rounded-lg border border-dashed">
              <div className="flex items-center gap-2 text-sm">
                <div className="text-muted-foreground">{selectedPaperType.icon}</div>
                <span className="font-medium">{selectedPaperType.label}</span>
                {selectedPaperType.recommended && (
                  <Badge variant="secondary" className="text-xs bg-primary/10 text-primary">
                    Recommended
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-1">{selectedPaperType.description}</p>
            </div>
          )}
        </div>

        {!hideProcessOptions && (
          <>
            <Separator />

            {/* Processing Options */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium flex items-center gap-2">
                <Shield className="h-4 w-4" />
                Processing Settings
              </h4>

              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <Checkbox
                    id="process-references"
                    checked={processReferences}
                    onCheckedChange={(checked) => onOptionsChange({ ...options, processReferences: !!checked })}
                    className="mt-0.5"
                  />
                  <div className="flex-1 space-y-1">
                    <Label
                      htmlFor="process-references"
                      className="flex items-center gap-2 text-sm font-medium cursor-pointer"
                    >
                      Process References
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger>
                            <HelpCircle className="h-4 w-4 text-muted-foreground" />
                          </TooltipTrigger>
                          <TooltipContent side="right" className="max-w-xs">
                            <p>Extract and process all references from the paper using AI-powered parsing</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Extract and parse all bibliographic references from the document
                    </p>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <Checkbox
                    id="validate-all"
                    checked={validateAll}
                    onCheckedChange={(checked) => onOptionsChange({ ...options, validateAll: !!checked })}
                    className="mt-0.5"
                    disabled={!processReferences}
                  />
                  <div className="flex-1 space-y-1">
                    <Label
                      htmlFor="validate-all"
                      className={`flex items-center gap-2 text-sm font-medium cursor-pointer ${
                        !processReferences ? "text-muted-foreground" : ""
                      }`}
                    >
                      Validate All References
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger>
                            <HelpCircle className="h-4 w-4 text-muted-foreground" />
                          </TooltipTrigger>
                          <TooltipContent side="right" className="max-w-xs">
                            <p>Validate and enrich references using multiple academic APIs for higher accuracy</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </Label>
                    <p className={`text-xs ${!processReferences ? "text-muted-foreground" : "text-muted-foreground"}`}>
                      Cross-reference with academic databases for validation and enrichment
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <Separator />
          </>
        )}

        {/* API Sources Information */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium flex items-center gap-2">
            <Database className="h-4 w-4" />
            Data Sources
          </h4>

          <div className="grid grid-cols-2 gap-2">
            <div className="flex items-center gap-2 p-2 bg-muted/30 rounded-md">
              <div className="w-2 h-2 bg-success rounded-full" />
              <span className="text-xs font-medium">CrossRef</span>
            </div>
            <div className="flex items-center gap-2 p-2 bg-muted/30 rounded-md">
              <div className="w-2 h-2 bg-success rounded-full" />
              <span className="text-xs font-medium">OpenAlex</span>
            </div>
            <div className="flex items-center gap-2 p-2 bg-muted/30 rounded-md">
              <div className="w-2 h-2 bg-success rounded-full" />
              <span className="text-xs font-medium">Semantic Scholar</span>
            </div>
            <div className="flex items-center gap-2 p-2 bg-muted/30 rounded-md">
              <div className="w-2 h-2 bg-success rounded-full" />
              <span className="text-xs font-medium">PubMed</span>
            </div>
            <div className="flex items-center gap-2 p-2 bg-muted/30 rounded-md">
              <div className="w-2 h-2 bg-success rounded-full" />
              <span className="text-xs font-medium">DOAJ</span>
            </div>
          </div>

          <div className="p-3 bg-primary/5 rounded-lg border border-primary/20">
            <div className="flex items-center gap-2 text-sm text-primary mb-1">
              <Clock className="h-4 w-4" />
              <span className="font-medium">Processing Time</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Estimated processing time: 2-5 minutes depending on paper length and validation options
            </p>
          </div>
        </div>

        {/* Advanced Settings Hint */}
        <div className="pt-2 border-t border-dashed">
          <p className="text-xs text-muted-foreground text-center">
            Advanced configuration options will be available after processing
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
