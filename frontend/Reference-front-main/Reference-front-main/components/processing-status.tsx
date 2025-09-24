"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { CheckCircle, Clock, Upload, Search, Database, AlertCircle, Loader2, Play, Pause } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"

interface ProcessingStep {
  id: string
  label: string
  description: string
  icon: React.ReactNode
  status: "pending" | "processing" | "completed" | "error"
  progress?: number
  duration?: number
  details?: string[]
}

interface ProcessingStatusProps {
  isVisible?: boolean
  onCancel?: () => void
}

export function ProcessingStatus({ isVisible = false, onCancel }: ProcessingStatusProps) {
  const [progress, setProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState(0)
  const [startTime, setStartTime] = useState<Date | null>(null)
  const [elapsedTime, setElapsedTime] = useState(0)
  const [isPaused, setIsPaused] = useState(false)

  const steps: ProcessingStep[] = [
    {
      id: "upload",
      label: "File Upload",
      description: "Uploading and validating document",
      icon: <Upload className="h-4 w-4" />,
      status: currentStep > 0 ? "completed" : currentStep === 0 ? "processing" : "pending",
      progress: currentStep > 0 ? 100 : currentStep === 0 ? progress : 0,
      details: ["Validating file format", "Checking file integrity", "Preparing for processing"],
    },
    {
      id: "extraction",
      label: "Reference Extraction",
      description: "Extracting references using AI parsing",
      icon: <Search className="h-4 w-4" />,
      status: currentStep > 1 ? "completed" : currentStep === 1 ? "processing" : "pending",
      progress: currentStep > 1 ? 100 : currentStep === 1 ? progress : 0,
      details: ["Analyzing document structure", "Identifying reference sections", "Parsing individual references"],
    },
    {
      id: "enrichment",
      label: "API Enrichment",
      description: "Validating with academic databases",
      icon: <Database className="h-4 w-4" />,
      status: currentStep > 2 ? "completed" : currentStep === 2 ? "processing" : "pending",
      progress: currentStep > 2 ? 100 : currentStep === 2 ? progress : 0,
      details: ["Querying CrossRef API", "Searching OpenAlex database", "Validating with Semantic Scholar"],
    },
  ]

  // Simulate processing progress
  useEffect(() => {
    if (!isVisible || isPaused) return

    if (!startTime) {
      setStartTime(new Date())
    }

    const interval = setInterval(() => {
      setElapsedTime((prev) => prev + 1)

      setProgress((prev) => {
        if (prev >= 100) {
          if (currentStep < steps.length - 1) {
            setCurrentStep((curr) => curr + 1)
            return 0
          }
          return 100
        }
        return prev + Math.random() * 3 + 1
      })
    }, 500)

    return () => clearInterval(interval)
  }, [isVisible, currentStep, steps.length, isPaused, startTime])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  const togglePause = () => {
    setIsPaused(!isPaused)
  }

  const currentStepData = steps[currentStep]
  const isCompleted = currentStep >= steps.length - 1 && progress >= 100

  if (!isVisible) return null

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <div className="p-1 bg-primary/20 rounded-full">
              {isCompleted ? (
                <CheckCircle className="h-5 w-5 text-success" />
              ) : (
                <Loader2 className="h-5 w-5 text-primary animate-spin" />
              )}
            </div>
            Processing Status
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-primary border-primary/20">
              {isCompleted ? "Completed" : isPaused ? "Paused" : "Processing"}
            </Badge>
            <Badge variant="secondary" className="text-xs">
              {formatTime(elapsedTime)}
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Overall Progress */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Overall Progress</span>
            <span className="text-muted-foreground">
              {Math.round(((currentStep * 100 + progress) / (steps.length * 100)) * 100)}%
            </span>
          </div>
          <Progress value={((currentStep * 100 + progress) / (steps.length * 100)) * 100} className="w-full h-2" />
        </div>

        <Separator />

        {/* Processing Steps */}
        <div className="space-y-4">
          {steps.map((step, index) => (
            <div key={step.id} className="space-y-2">
              <div className="flex items-center gap-3">
                <div
                  className={`
                    p-2 rounded-full transition-all duration-300
                    ${step.status === "completed" ? "bg-success/10 text-success" : ""}
                    ${step.status === "processing" ? "bg-primary/10 text-primary" : ""}
                    ${step.status === "pending" ? "bg-muted text-muted-foreground" : ""}
                    ${step.status === "error" ? "bg-destructive/10 text-destructive" : ""}
                  `}
                >
                  {step.status === "completed" ? (
                    <CheckCircle className="h-4 w-4" />
                  ) : step.status === "processing" ? (
                    <div className="relative">
                      {step.icon}
                      {!isPaused && <div className="absolute inset-0 animate-ping rounded-full bg-primary/20" />}
                    </div>
                  ) : step.status === "error" ? (
                    <AlertCircle className="h-4 w-4" />
                  ) : (
                    step.icon
                  )}
                </div>

                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span
                      className={`
                        font-medium transition-colors
                        ${step.status === "completed" ? "text-success" : ""}
                        ${step.status === "processing" ? "text-primary" : ""}
                        ${step.status === "pending" ? "text-muted-foreground" : ""}
                        ${step.status === "error" ? "text-destructive" : ""}
                      `}
                    >
                      {step.label}
                    </span>
                    {step.status === "processing" && (
                      <Badge variant="outline" className="text-xs">
                        {Math.round(step.progress || 0)}%
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{step.description}</p>
                </div>
              </div>

              {/* Step Progress Bar */}
              {step.status === "processing" && (
                <div className="ml-11">
                  <Progress value={step.progress || 0} className="w-full h-1" />
                </div>
              )}

              {/* Step Details */}
              {step.status === "processing" && step.details && (
                <div className="ml-11 space-y-1">
                  {step.details.map((detail, detailIndex) => (
                    <div key={detailIndex} className="flex items-center gap-2 text-xs text-muted-foreground">
                      <div
                        className={`w-1 h-1 rounded-full ${
                          detailIndex <= (step.progress || 0) / 33 ? "bg-primary" : "bg-muted"
                        }`}
                      />
                      {detail}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        <Separator />

        {/* Current Status Message */}
        <div className="p-3 bg-muted/30 rounded-lg">
          <div className="flex items-center gap-2 text-sm font-medium mb-1">
            <Clock className="h-4 w-4 text-primary" />
            Current Status
          </div>
          <p className="text-sm text-muted-foreground">
            {isCompleted
              ? "Processing completed successfully! Results are ready for review."
              : isPaused
                ? `Processing paused at ${currentStepData?.label}. Click resume to continue.`
                : `${currentStepData?.description}... This may take a few minutes.`}
          </p>
        </div>

        {/* Control Buttons */}
        <div className="flex items-center justify-between pt-2">
          <div className="text-xs text-muted-foreground">
            {isCompleted ? `Completed in ${formatTime(elapsedTime)}` : `Elapsed: ${formatTime(elapsedTime)}`}
          </div>

          <div className="flex items-center gap-2">
            {!isCompleted && (
              <>
                <Button variant="outline" size="sm" onClick={togglePause} className="text-xs bg-transparent">
                  {isPaused ? (
                    <>
                      <Play className="h-3 w-3 mr-1" />
                      Resume
                    </>
                  ) : (
                    <>
                      <Pause className="h-3 w-3 mr-1" />
                      Pause
                    </>
                  )}
                </Button>
                {onCancel && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onCancel}
                    className="text-xs text-destructive hover:text-destructive bg-transparent"
                  >
                    Cancel
                  </Button>
                )}
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
