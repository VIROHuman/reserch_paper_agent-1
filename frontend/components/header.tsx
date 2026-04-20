"use client"

import { FileText, Activity, AlertCircle, User, LogIn } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { useHealthCheck } from "@/hooks/use-api"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import Image from "next/image"
import Link from "next/link"
import { useAuth } from "@/context/auth-context"
import { Button } from "@/components/ui/button"

export function Header() {
  const { isHealthy, loading: healthLoading, error } = useHealthCheck()
  const { isAuthenticated: auth, user } = useAuth()

  const getStatusBadge = () => {
    if (healthLoading) {
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
          <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <div className="p-2 bg-primary/10 rounded-lg">
              <FileText className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-semibold">Reference Agent</h1>
              <p className="text-sm text-muted-foreground">Academic Research Tool</p>
            </div>
          </Link>

          <div className="flex items-center gap-4">
            {getStatusBadge()}
            <div className="h-6 w-px bg-border mx-1" />
            {auth ? (
              <Link href="/profile">
                <Button variant="ghost" size="sm" className="gap-2">
                  <User className="h-4 w-4" />
                  <span className="hidden sm:inline">Profile</span>
                </Button>
              </Link>
            ) : (
              <Link href="/login">
                <Button variant="default" size="sm" className="gap-2">
                  <LogIn className="h-4 w-4" />
                  <span>Login</span>
                </Button>
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
