"use client"

import { FileText, Activity, AlertCircle } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { useHealthCheck } from "@/hooks/use-api"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import Image from "next/image"

export function Header() {
  const { isHealthy, loading, error } = useHealthCheck()

  const getStatusBadge = () => {
    if (loading) {
      return (
        <Badge variant="outline" className="text-muted-foreground border-muted-foreground/20">
          <Activity className="h-3 w-3 mr-1 animate-pulse" />
          Checking...
        </Badge>
      )
    }

    if (error || !isHealthy) {
      return (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger>
              <Badge variant="outline" className="text-destructive border-destructive/20">
                <AlertCircle className="h-3 w-3 mr-1" />
                API Offline
              </Badge>
            </TooltipTrigger>
            <TooltipContent>
              <p>Unable to connect to processing server</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )
    }

    return (
      <Badge variant="outline" className="text-success border-success/20">
        <Activity className="h-3 w-3 mr-1" />
        API Connected
      </Badge>
    )
  }

  return (
    <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4 max-w-6xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <Image
                src="/images/tnq-tech-logo.jpg"
                alt="TNQ Tech - A Lumina Datamatics Company"
                width={120}
                height={40}
                className="h-10 w-auto"
              />
            </div>

            <div className="h-8 w-px bg-border" />

            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-lg">
                <FileText className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h1 className="text-xl font-semibold">Reference Agent</h1>
                <p className="text-sm text-muted-foreground">Academic Research Tool</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">{getStatusBadge()}</div>
        </div>
      </div>
    </header>
  )
}
