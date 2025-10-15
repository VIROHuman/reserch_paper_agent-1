"use client"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { ArrowRight, Plus, Edit, Check } from "lucide-react"
import { ValidationChange } from "@/lib/api"

interface ValidationChangesViewProps {
  changes?: ValidationChange[]
  referenceIndex: number
}

export function ValidationChangesView({ changes, referenceIndex }: ValidationChangesViewProps) {
  if (!changes || changes.length === 0) {
    return null
  }

  // Filter out unchanged fields for cleaner display
  const meaningfulChanges = changes.filter(c => c.type !== "unchanged")

  if (meaningfulChanges.length === 0) {
    return (
      <div className="p-3 rounded-lg bg-muted/30 border border-dashed">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Check className="h-4 w-4" />
          <span>No changes - reference was already complete</span>
        </div>
      </div>
    )
  }

  const getChangeIcon = (type: string) => {
    switch (type) {
      case "added":
        return <Plus className="h-3 w-3 text-green-600" />
      case "updated":
        return <Edit className="h-3 w-3 text-blue-600" />
      default:
        return <Check className="h-3 w-3 text-gray-600" />
    }
  }

  const getChangeBadgeColor = (type: string) => {
    switch (type) {
      case "added":
        return "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400"
      case "updated":
        return "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400"
      default:
        return "bg-gray-100 text-gray-700 dark:bg-gray-950 dark:text-gray-400"
    }
  }

  const formatValue = (value: any): string => {
    if (value === null || value === undefined || value === "") {
      return "(empty)"
    }
    if (Array.isArray(value)) {
      return value.length > 0 ? value.join(", ") : "(empty)"
    }
    return String(value)
  }

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <ArrowRight className="h-4 w-4 text-primary" />
          Validation Changes for Reference #{referenceIndex + 1}
          <Badge variant="outline" className="ml-auto">
            {meaningfulChanges.length} change{meaningfulChanges.length !== 1 ? "s" : ""}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {meaningfulChanges.map((change, idx) => (
          <div key={idx} className="space-y-2">
            <div className="flex items-center gap-2">
              {getChangeIcon(change.type)}
              <span className="text-sm font-medium capitalize">{change.field.replace(/_/g, " ")}</span>
              <Badge variant="outline" className={`text-xs ${getChangeBadgeColor(change.type)}`}>
                {change.type}
              </Badge>
            </div>
            
            <div className="ml-5 grid grid-cols-1 gap-2 text-xs">
              {change.type === "added" ? (
                <div className="p-2 rounded bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800">
                  <div className="text-green-600 dark:text-green-400 font-medium mb-1">Added:</div>
                  <div className="text-foreground">{formatValue(change.after)}</div>
                </div>
              ) : change.type === "updated" ? (
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2 rounded bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800">
                    <div className="text-red-600 dark:text-red-400 font-medium mb-1">Before:</div>
                    <div className="text-foreground line-through opacity-70">{formatValue(change.before)}</div>
                  </div>
                  <div className="p-2 rounded bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800">
                    <div className="text-blue-600 dark:text-blue-400 font-medium mb-1">After:</div>
                    <div className="text-foreground">{formatValue(change.after)}</div>
                  </div>
                </div>
              ) : null}
            </div>
            
            {idx < meaningfulChanges.length - 1 && <Separator className="mt-3" />}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

