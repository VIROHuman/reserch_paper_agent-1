"use client"

import { useState, useCallback } from "react"
import { useDropzone } from "react-dropzone"
import { Upload, File, X, CheckCircle, AlertCircle, Loader2 } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface UploadedFile {
  file: File
  preview?: string
}

interface FileValidationError {
  type: "size" | "type" | "general"
  message: string
}

interface FileUploadSectionProps {
  onFileProcess: (file: File, useStreaming?: boolean) => void
  buttonText?: string
  buttonIcon?: React.ReactNode
}

export function FileUploadSection({ 
  onFileProcess, 
  buttonText = "Process File",
  buttonIcon 
}: FileUploadSectionProps) {
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [validationError, setValidationError] = useState<FileValidationError | null>(null)

  const validateFile = (file: File): FileValidationError | null => {
    // Check file size (50MB limit)
    if (file.size > 50 * 1024 * 1024) {
      return {
        type: "size",
        message: "File size exceeds 50MB limit. Please choose a smaller file.",
      }
    }

    // Check file type
    const allowedTypes = [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/msword",
    ]
    if (!allowedTypes.includes(file.type)) {
      return {
        type: "type",
        message: "Invalid file type. Please upload a PDF, DOCX, or DOC file.",
      }
    }

    return null
  }

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    setValidationError(null)

    if (rejectedFiles.length > 0) {
      const rejection = rejectedFiles[0]
      if (rejection.errors[0]?.code === "file-too-large") {
        setValidationError({
          type: "size",
          message: "File size exceeds 50MB limit. Please choose a smaller file.",
        })
      } else if (rejection.errors[0]?.code === "file-invalid-type") {
        setValidationError({
          type: "type",
          message: "Invalid file type. Please upload a PDF, DOCX, or DOC file.",
        })
      } else {
        setValidationError({
          type: "general",
          message: "File upload failed. Please try again.",
        })
      }
      return
    }

    const file = acceptedFiles[0]
    if (file) {
      const error = validateFile(file)
      if (error) {
        setValidationError(error)
        return
      }

      setUploadedFile({ file })
      simulateUpload()
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "application/msword": [".doc"],
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024, // 50MB
    disabled: isUploading,
  })

  const simulateUpload = () => {
    setIsUploading(true)
    setUploadProgress(0)

    const interval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval)
          setIsUploading(false)
          return 100
        }
        return prev + 10
      })
    }, 200)
  }

  const removeFile = () => {
    setUploadedFile(null)
    setUploadProgress(0)
    setValidationError(null)
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes"
    const k = 1024
    const sizes = ["Bytes", "KB", "MB", "GB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Number.parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
  }

  const getFileTypeLabel = (type: string) => {
    switch (type) {
      case "application/pdf":
        return "PDF"
      case "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return "DOCX"
      case "application/msword":
        return "DOC"
      default:
        return "Unknown"
    }
  }

  return (
    <Card>
      <CardContent className="p-6">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Upload className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Upload Research Paper</h2>
          </div>

          {validationError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{validationError.message}</AlertDescription>
            </Alert>
          )}

          {!uploadedFile ? (
            <div
              {...getRootProps()}
              className={`
                border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all duration-200
                ${isDragActive && !isDragReject ? "border-primary bg-primary/5 scale-[1.02]" : ""}
                ${isDragReject ? "border-destructive bg-destructive/5" : ""}
                ${!isDragActive && !isDragReject ? "border-border hover:border-primary/50 hover:bg-muted/50" : ""}
                ${isUploading ? "pointer-events-none opacity-50" : ""}
              `}
            >
              <input {...getInputProps()} />
              <div className="space-y-4">
                <div
                  className={`
                  mx-auto w-12 h-12 rounded-full flex items-center justify-center transition-colors
                  ${isDragActive && !isDragReject ? "bg-primary/20" : "bg-primary/10"}
                  ${isDragReject ? "bg-destructive/10" : ""}
                `}
                >
                  <Upload
                    className={`
                    h-6 w-6 transition-colors
                    ${isDragActive && !isDragReject ? "text-primary" : "text-primary"}
                    ${isDragReject ? "text-destructive" : ""}
                  `}
                  />
                </div>
                <div className="space-y-2">
                  <p className="text-lg font-medium">
                    {isDragActive && !isDragReject
                      ? "Drop your file here"
                      : isDragReject
                        ? "Invalid file type"
                        : "Drag & drop your research paper"}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {isDragReject ? "Please upload a PDF, DOCX, or DOC file" : "or click to browse files"}
                  </p>
                </div>
                <div className="flex flex-wrap justify-center gap-2">
                  <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">
                    PDF
                  </Badge>
                  <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">
                    DOCX
                  </Badge>
                  <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">
                    DOC
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">Maximum file size: 50MB</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-3 p-4 bg-muted/50 rounded-lg border">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <File className="h-6 w-6 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{uploadedFile.file.name}</p>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>{formatFileSize(uploadedFile.file.size)}</span>
                    <span>•</span>
                    <Badge variant="outline" className="text-xs">
                      {getFileTypeLabel(uploadedFile.file.type)}
                    </Badge>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {isUploading ? (
                    <Loader2 className="h-5 w-5 text-primary animate-spin" />
                  ) : (
                    <CheckCircle className="h-5 w-5 text-success" />
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={removeFile}
                    className="text-muted-foreground hover:text-destructive"
                    disabled={isUploading}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              {isUploading && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Uploading...</span>
                    <span className="font-medium">{uploadProgress}%</span>
                  </div>
                  <Progress value={uploadProgress} className="w-full" />
                </div>
              )}

              <Button 
                className="w-full" 
                size="lg" 
                disabled={isUploading}
                onClick={() => {
                  console.log("[DEBUG] Parse button clicked, isUploading:", isUploading, "uploadedFile:", uploadedFile)
                  if (uploadedFile && !isUploading) {
                    console.log("[DEBUG] Calling onFileProcess with file:", uploadedFile.file.name)
                    onFileProcess(uploadedFile.file, true)
                  } else {
                    console.log("[DEBUG] Button click blocked - isUploading or no file")
                  }
                }}
              >
                {isUploading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Uploading... ({uploadProgress}%)
                  </>
                ) : (
                  <>
                    {buttonIcon && <span className="mr-2">{buttonIcon}</span>}
                    {buttonText}
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Upload Tips */}
          <div className="mt-6 p-4 bg-muted/30 rounded-lg border border-dashed">
            <h4 className="text-sm font-medium mb-2">Upload Tips:</h4>
            <ul className="text-xs text-muted-foreground space-y-1">
              <li>• Ensure your paper has a clear reference section</li>
              <li>• Higher quality PDFs produce better extraction results</li>
              <li>• Processing time varies based on paper length and complexity</li>
              <li>• Supported formats: PDF, DOCX, DOC (up to 50MB)</li>
            </ul>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
