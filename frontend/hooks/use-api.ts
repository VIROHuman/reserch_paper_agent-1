"use client"

import { useState, useEffect } from "react"
import { apiClient, type HealthCheckData, type ProcessingData, type SupportedTypesData, type ProcessingProgress } from "@/lib/api"

export function useHealthCheck() {
  const [data, setData] = useState<HealthCheckData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        setLoading(true)
        const response = await apiClient.healthCheck()
        if (response.success) {
          setData(response.data)
          setError(null)
        } else {
          setError(response.message)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Health check failed")
      } finally {
        setLoading(false)
      }
    }

    checkHealth()

    // Check health every 30 seconds
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  return { data, loading, error, isHealthy: data?.status === "healthy" }
}

export function useFileProcessing() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<ProcessingData | null>(null)
  const [progress, setProgress] = useState<ProcessingProgress | null>(null)

  const processFile = async (
    file: File,
    options: {
      processReferences?: boolean
      validateAll?: boolean
      paperType?: string
      useStreaming?: boolean
    } = {},
  ) => {
    try {
      setLoading(true)
      setError(null)
      setProgress(null)

      if (options.useStreaming) {
        // Use streaming upload for better progress tracking
        const response = await apiClient.uploadWithProgress(
          file,
          options.processReferences ?? true,
          options.validateAll ?? true,
          options.paperType ?? "auto",
          (progressUpdate) => {
            setProgress(progressUpdate)
          }
        )

        if (response.success) {
          setData(response.data)
          setProgress(null)
          return response.data
        } else {
          setError(response.message)
          return null
        }
      } else {
        // Fallback to regular upload for smaller files
        const response = await apiClient.uploadAndProcess(
          file,
          options.processReferences ?? true,
          options.validateAll ?? true,
          options.paperType ?? "auto",
        )

        if (response.success) {
          setData(response.data)
          return response.data
        } else {
          setError(response.message)
          return null
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Processing failed"
      setError(errorMessage)
      return null
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setData(null)
    setError(null)
    setLoading(false)
    setProgress(null)
  }

  return {
    processFile,
    loading,
    error,
    data,
    progress,
    reset,
  }
}

export function useSupportedTypes() {
  const [data, setData] = useState<SupportedTypesData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchSupportedTypes = async () => {
      try {
        setLoading(true)
        const response = await apiClient.getSupportedTypes()
        if (response.success) {
          setData(response.data)
          setError(null)
        } else {
          setError(response.message)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch supported types")
      } finally {
        setLoading(false)
      }
    }

    fetchSupportedTypes()
  }, [])

  return { data, loading, error }
}
