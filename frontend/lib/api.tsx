// API client for Research Paper Reference Agent
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api"

export interface ApiResponse<T> {
  success: boolean
  message: string
  data: T
}

export interface HealthCheckData {
  status: string
  utilities_initialized: boolean
  available_processors: {
    pdf_processor: boolean
    word_processor: boolean
    file_handler: boolean
    grobid_client: boolean
    enhanced_parser: boolean
  }
}

export interface FileInfo {
  filename: string
  size: number
  type: string
  references_found: number
  successfully_processed: number
}

export interface ProcessingSummary {
  total_references: number
  successfully_processed: number
  total_extracted_fields: number
  total_missing_fields: number
  enriched_count: number
}

export interface ExtractedFields {
  family_names: string[]
  given_names: string[]
  full_names?: string[]  // NEW: Full author names like ["John Smith", "Jane Doe"]
  year: number
  title: string
  journal: string
  doi: string
  pages: string
  publisher: string
  url: string
  abstract: string
}

export interface QualityMetrics {
  quality_improvement: number
  final_quality_score: number
}

export interface FlaggingAnalysis {
  missing_fields: string[]
  replaced_fields: string[]
  conflicted_fields: string[]
  partial_fields: string[]
  data_sources_used: string[]
}

export interface ProcessingResult {
  index: number
  original_text: string
  parser_used: string
  api_enrichment_used: boolean
  enrichment_sources: string[]
  extracted_fields: ExtractedFields
  quality_metrics: QualityMetrics
  missing_fields: string[]
  tagged_output: string
  flagging_analysis: FlaggingAnalysis
  error?: string
}

export interface ProcessingData {
  file_info: FileInfo
  paper_type: string
  summary: ProcessingSummary
  processing_results: ProcessingResult[]
}

export interface SupportedTypesData {
  supported_paper_types: string[]
  supported_file_types: string[]
  description: string
}

export interface ExtractOnlyData {
  file_info: FileInfo
  paper_type: string
  references: string[]
  paper_data: any
}

export interface ValidationChange {
  field: string
  type: "added" | "updated" | "unchanged"
  before: any
  after: any
}

export interface ParsedReference {
  index: number
  original_text: string
  parser_used: string
  extracted_fields: ExtractedFields
  quality_metrics: {
    initial_quality_score?: number
    quality_improvement?: number
    final_quality_score?: number
  }
  missing_fields: string[]
  tagged_output: string
  error?: string
  api_enrichment_used?: boolean
  enrichment_sources?: string[]
  from_cache?: boolean
  validation_changes?: ValidationChange[]  // NEW: Track what changed during validation
}

export interface ParseSummary {
  total_references: number
  successfully_parsed: number
  total_extracted_fields: number
  total_missing_fields: number
  needs_validation: number
}

export interface ParsedBatchData {
  batch_id: string
  file_info: FileInfo
  processing_time: string
  summary: ParseSummary
  parsed_references: ParsedReference[]
}

export interface BatchInfo {
  batch_id: string
  file_info: FileInfo
  parsed_references: ParsedReference[]
  created_at: string
  validation_status: string
  validation_result: any
  paper_type: string
  reference_count: number
}

export interface ValidationProgress {
  type: "progress" | "result" | "complete" | "error"
  progress?: number
  current?: number
  total?: number
  message?: string
  index?: number
  data?: ParsedReference
  results?: ParsedReference[]
  summary?: {
    total_references: number
    validated: number
    enriched: number
    from_cache: number
    cache_stats: any
  }
}

export type ValidationMode = "quick" | "standard" | "thorough" | "custom"

export interface ProcessingProgress {
  job_id: string
  status: "uploading" | "processing" | "completed" | "error"
  progress: number
  current_step: string
  message: string
  processed_references?: number
  total_references?: number
}

export interface JobStatus {
  job_id: string
  status: "pending" | "processing" | "completed" | "failed" | "cancelled"
  progress: number
  current_step: string
  message: string
  created_at: string
  updated_at: string
  result?: ProcessingData
  error?: string
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<ApiResponse<T>> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 300000) // 5 minute timeout for long operations

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
        },
        signal: controller.signal,
        ...options,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      return data
    } catch (error) {
      clearTimeout(timeoutId)
      console.error("API request failed:", error)
      throw error
    }
  }

  private async uploadRequest<T>(endpoint: string, formData: FormData): Promise<ApiResponse<T>> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 1800000) // 30 minute timeout for uploads and processing

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      return data
    } catch (error) {
      clearTimeout(timeoutId)
      console.error("Upload request failed:", error)
      throw error
    }
  }

  async healthCheck(): Promise<ApiResponse<HealthCheckData>> {
    const result = await this.request<HealthCheckData>("/health")
    console.log("[API] Health check successful")
    return result
  }

  // Upload and process file
  async uploadAndProcess(
    file: File,
    processReferences = true,
    validateAll = true,
    paperType = "auto",
  ): Promise<ApiResponse<ProcessingData>> {
    try {
      const formData = new FormData()
      formData.append("file", file)
      formData.append("process_references", processReferences.toString())
      formData.append("validate_all", validateAll.toString())
      formData.append("paper_type", paperType)

      console.log("[API] Uploading and processing file:", file.name)
      const result = await this.uploadRequest<ProcessingData>("/upload-pdf", formData)
      console.log("[API] File processing completed successfully")
      return result
    } catch (error) {
      console.error("[API] File processing failed:", error)
      throw error
    }
  }

  // Extract references only
  async extractReferencesOnly(file: File, paperType = "auto"): Promise<ApiResponse<ExtractOnlyData>> {
    try {
      const formData = new FormData()
      formData.append("file", file)
      formData.append("paper_type", paperType)

      console.log("[API] Extracting references from file:", file.name)
      const result = await this.uploadRequest<ExtractOnlyData>("/extract-references-only", formData)
      console.log("[API] Reference extraction completed successfully")
      return result
    } catch (error) {
      console.error("[API] Reference extraction failed:", error)
      throw error
    }
  }

  // Get supported types
  async getSupportedTypes(): Promise<ApiResponse<SupportedTypesData>> {
    const result = await this.request<SupportedTypesData>("/supported-paper-types")
    console.log("[API] Supported types fetched successfully")
    return result
  }

  // Upload file with async job processing
  async uploadWithAsyncJob(
    file: File,
    processReferences = true,
    validateAll = true,
    paperType = "auto",
    onProgress?: (progress: ProcessingProgress) => void
  ): Promise<ApiResponse<ProcessingData>> {
    try {
      const formData = new FormData()
      formData.append("file", file)
      formData.append("process_references", processReferences.toString())
      formData.append("validate_all", validateAll.toString())
      formData.append("paper_type", paperType)

      console.log("[API] Uploading file with async job processing:", file.name)
      
      // Submit job and get job ID
      const response = await fetch(`${this.baseUrl}/upload-pdf-async`, {
        method: "POST",
        body: formData,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const jobResponse = await response.json()
      if (!jobResponse.success) {
        throw new Error(jobResponse.message || "Job submission failed")
      }

      const jobId = jobResponse.data.job_id
      console.log("[API] Job submitted with ID:", jobId)

      // Poll for job completion
      return await this.pollJobStatus(jobId, onProgress)
    } catch (error) {
      console.error("[API] Async job processing failed:", error)
      throw error
    }
  }

  // Poll job status until completion
  private async pollJobStatus(
    jobId: string,
    onProgress?: (progress: ProcessingProgress) => void
  ): Promise<ApiResponse<ProcessingData>> {
    const maxAttempts = 120 // 10 minutes with 5-second intervals
    let attempts = 0

    while (attempts < maxAttempts) {
      try {
        const response = await fetch(`${this.baseUrl}/job-status/${jobId}`)
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const statusResponse = await response.json()
        if (!statusResponse.success) {
          throw new Error(statusResponse.message || "Failed to get job status")
        }

        const job = statusResponse.data
        
        // Update progress if callback provided
        if (onProgress) {
          onProgress({
            job_id: job.job_id,
            status: job.status as "uploading" | "processing" | "completed" | "error",
            progress: job.progress,
            current_step: job.current_step,
            message: job.message,
            processed_references: 0, // Will be updated from result
            total_references: 0 // Will be updated from result
          })
        }

        if (job.status === "completed") {
          console.log("[API] Job completed successfully")
          return {
            success: true,
            message: job.message,
            data: job.result
          }
        } else if (job.status === "failed") {
          throw new Error(job.error || "Job processing failed")
        }

        // Wait 5 seconds before next poll
        await new Promise(resolve => setTimeout(resolve, 5000))
        attempts++
      } catch (error) {
        console.error("[API] Error polling job status:", error)
        throw error
      }
    }

    throw new Error("Job processing timeout")
  }

  // Upload file with streaming progress (legacy)
  async uploadWithProgress(
    file: File,
    processReferences = true,
    validateAll = true,
    paperType = "auto",
    onProgress?: (progress: ProcessingProgress) => void
  ): Promise<ApiResponse<ProcessingData>> {
    try {
      const formData = new FormData()
      formData.append("file", file)
      formData.append("process_references", processReferences.toString())
      formData.append("validate_all", validateAll.toString())
      formData.append("paper_type", paperType)

      console.log("[API] Uploading file with progress tracking:", file.name)
      
      // Use streaming endpoint for better progress tracking
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 1800000) // 30 minute timeout
      
      const response = await fetch(`${this.baseUrl}/upload-pdf-stream`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      })
      
      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      // Check if response is streaming (Server-Sent Events)
      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('text/event-stream')) {
        return await this.handleStreamingResponse(response, onProgress)
      } else {
        // Fallback to regular JSON response
        const data = await response.json()
        console.log("[API] File processing completed successfully")
        return data
      }
    } catch (error) {
      clearTimeout(timeoutId)
      console.error("[API] File processing failed:", error)
      throw error
    }
  }

  private async handleStreamingResponse(
    response: Response,
    onProgress?: (progress: ProcessingProgress) => void
  ): Promise<ApiResponse<ProcessingData>> {
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error("No response body reader available")
    }

    const decoder = new TextDecoder()
    let finalResult: ApiResponse<ProcessingData> | null = null

    try {
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              
              if (data.type === 'progress' && onProgress) {
                onProgress(data.data as ProcessingProgress)
              } else if (data.type === 'complete') {
                finalResult = data.data as ApiResponse<ProcessingData>
              } else if (data.type === 'error') {
                throw new Error(data.message || 'Processing failed')
              }
            } catch (parseError) {
              console.warn("[API] Failed to parse streaming data:", parseError)
            }
          }
        }
      }

      if (!finalResult) {
        throw new Error("No final result received from streaming response")
      }

      console.log("[API] Streaming processing completed successfully")
      return finalResult
    } finally {
      reader.releaseLock()
    }
  }

  // Check job status
  async getJobStatus(jobId: string): Promise<ApiResponse<JobStatus>> {
    const result = await this.request<JobStatus>(`/job-status/${jobId}`)
    console.log(`[API] Job status fetched for ${jobId}`)
    return result
  }

  // Cancel job
  async cancelJob(jobId: string): Promise<ApiResponse<{ cancelled: boolean }>> {
    const result = await this.request<{ cancelled: boolean }>(`/cancel-job/${jobId}`, {
      method: "POST"
    })
    console.log(`[API] Job cancellation requested for ${jobId}`)
    return result
  }

  // ===== NEW: Two-Step Workflow Methods =====

  // Step 1: Parse references only (no enrichment)
  async parseReferencesOnly(
    file: File,
    paperType = "auto"
  ): Promise<ApiResponse<ParsedBatchData>> {
    try {
      const formData = new FormData()
      formData.append("file", file)
      formData.append("paper_type", paperType)

      console.log("[API] Parsing references (no enrichment) from file:", file.name)
      const result = await this.uploadRequest<ParsedBatchData>("/parse-references", formData)
      console.log("[API] Reference parsing completed successfully, batch_id:", result.data.batch_id)
      return result
    } catch (error) {
      console.error("[API] Reference parsing failed:", error)
      throw error
    }
  }

  // Get batch information
  async getBatchInfo(batchId: string): Promise<ApiResponse<BatchInfo>> {
    try {
      console.log("[API] Fetching batch info for:", batchId)
      const result = await this.request<BatchInfo>(`/batch/${batchId}`)
      console.log("[API] Batch info retrieved successfully")
      return result
    } catch (error) {
      console.error("[API] Failed to get batch info:", error)
      throw error
    }
  }

  // Step 2: Validate batch with streaming progress
  async validateBatch(
    batchId: string,
    mode: ValidationMode = "standard",
    selectedIndices?: number[],
    onProgress?: (progress: ValidationProgress) => void
  ): Promise<ParsedReference[]> {
    try {
      const formData = new FormData()
      formData.append("mode", mode)
      if (selectedIndices && selectedIndices.length > 0) {
        formData.append("selected_indices", JSON.stringify(selectedIndices))
      }

      console.log(`[API] Starting validation for batch ${batchId} (mode: ${mode})`)
      
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 1800000) // 30 minute timeout
      
      const response = await fetch(`${this.baseUrl}/validate-batch/${batchId}`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      })
      
      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      // Handle streaming response
      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error("No response body reader available")
      }

      const decoder = new TextDecoder()
      let finalResults: ParsedReference[] = []
      let startTime = Date.now()
      const maxWaitTime = 300000 // 5 minutes
      let buffer = '' // Buffer for incomplete lines

      let eventsReceived = 0
      try {
        while (true) {
          // Check for timeout
          if (Date.now() - startTime > maxWaitTime) {
            console.error("[DEBUG] Validation timeout after 5 minutes")
            throw new Error("Validation timeout - no completion event received")
          }
          
          const { done, value } = await reader.read()
          
          if (done) {
            console.log(`[DEBUG] Stream ended after receiving ${eventsReceived} events`)
            console.log(`[DEBUG] finalResults.length = ${finalResults.length}`)
            console.log(`[DEBUG] Buffer remaining: ${buffer.length} chars`)
            
            // Process any remaining buffer data
            if (buffer.trim()) {
              if (buffer.startsWith('data: ')) {
                try {
                  const event: ValidationProgress = JSON.parse(buffer.slice(6))
                  console.log(`[DEBUG] Final buffered event:`, event.type)
                  if (onProgress) {
                    onProgress(event)
                  }
                  if (event.type === 'complete' && event.results) {
                    finalResults = event.results
                  }
                } catch (parseError) {
                  console.warn("[API] Failed to parse final buffer:", parseError)
                }
              }
            }
            
            break
          }

          const chunk = decoder.decode(value, { stream: true })
          buffer += chunk
          const lines = buffer.split('\n')
          buffer = lines.pop() || '' // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6)
              
              // Check for end-of-stream marker
              if (data.trim() === '[DONE]') {
                console.log("[DEBUG] ✅ End-of-stream marker received")
                break
              }
              
              try {
                eventsReceived++
                const event: ValidationProgress = JSON.parse(data)
                console.log(`[DEBUG] Event #${eventsReceived}:`, event.type, event)
                
                // Send progress update
                if (onProgress) {
                  onProgress(event)
                }
                
                // Store final results
                if (event.type === 'complete') {
                  console.log("[DEBUG] ✅ COMPLETE EVENT RECEIVED!")
                  console.log("[DEBUG] Event data:", event)
                  if (event.results) {
                    console.log("[DEBUG] Results available, length:", event.results.length)
                    finalResults = event.results
                  } else {
                    console.warn("[DEBUG] Complete event but no results array")
                  }
                } else if (event.type === 'error') {
                  console.error("[DEBUG] Error event received:", event.message)
                  throw new Error(event.message || 'Validation failed')
                } else if (event.type === 'result') {
                  console.log(`[DEBUG] Result event for ref ${event.index}`)
                } else {
                  console.log(`[DEBUG] ${event.type} event received`)
                }
              } catch (parseError) {
                console.warn("[API] Failed to parse validation event:", parseError)
                console.warn("[API] Raw line:", line)
              }
            }
          }
        }

        if (finalResults.length === 0) {
          console.error("[DEBUG] No results received from validation")
          console.error("[DEBUG] This might be due to the completion event not being received properly")
          throw new Error("No results received from validation")
        }

        console.log("[API] Validation completed successfully with", finalResults.length, "results")
        return finalResults
      } finally {
        reader.releaseLock()
      }
    } catch (error) {
      console.error("[API] Validation failed:", error)
      throw error
    }
  }

  // Get cache statistics
  async getCacheStats(): Promise<ApiResponse<any>> {
    try {
      const result = await this.request<any>("/cache-stats")
      console.log("[API] Cache stats retrieved")
      return result
    } catch (error) {
      console.error("[API] Failed to get cache stats:", error)
      throw error
    }
  }

  // Clear enrichment cache
  async clearCache(): Promise<ApiResponse<any>> {
    try {
      const result = await this.request<any>("/cache-clear", { method: "POST" })
      console.log("[API] Cache cleared successfully")
      return result
    } catch (error) {
      console.error("[API] Failed to clear cache:", error)
      throw error
    }
  }
}

// Export singleton instance
export const apiClient = new ApiClient()

// Export individual functions for convenience (with proper binding to preserve 'this' context)
export const healthCheck = apiClient.healthCheck.bind(apiClient)
export const uploadAndProcess = apiClient.uploadAndProcess.bind(apiClient)
export const uploadWithProgress = apiClient.uploadWithProgress.bind(apiClient)
export const extractReferencesOnly = apiClient.extractReferencesOnly.bind(apiClient)
export const getSupportedTypes = apiClient.getSupportedTypes.bind(apiClient)
export const getJobStatus = apiClient.getJobStatus.bind(apiClient)
export const cancelJob = apiClient.cancelJob.bind(apiClient)
export const parseReferencesOnly = apiClient.parseReferencesOnly.bind(apiClient)
export const getBatchInfo = apiClient.getBatchInfo.bind(apiClient)
export const validateBatch = apiClient.validateBatch.bind(apiClient)
export const getCacheStats = apiClient.getCacheStats.bind(apiClient)
export const clearCache = apiClient.clearCache.bind(apiClient)
