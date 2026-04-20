"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { User as LucideUser, LogOut, Shield, Mail, User as UserIcon, Calendar } from "lucide-react"
import { useAuth } from "@/context/auth-context"
import { ProtectedRoute } from "@/components/protected-route"

export default function ProfilePage() {
  const { user, logout, loading } = useAuth()
  const router = useRouter()

  const handleLogout = () => {
    logout()
    router.push("/login")
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <div className="w-16 h-16 bg-primary/20 rounded-full" />
          <div className="h-4 w-32 bg-muted rounded" />
        </div>
      </div>
    )
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-background flex flex-col">
        <Header />
        <main className="container mx-auto px-4 py-8 max-w-4xl flex-grow">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h1 className="text-3xl font-bold tracking-tight">User Profile</h1>
              <Button variant="outline" onClick={handleLogout} className="text-destructive hover:bg-destructive/10 border-destructive/20">
                <LogOut className="mr-2 h-4 w-4" />
                Sign Out
              </Button>
            </div>

            <div className="grid md:grid-cols-3 gap-6">
              <Card className="md:col-span-1 shadow-md bg-card/50">
                <CardContent className="pt-6 text-center">
                  <div className="mx-auto w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                    <UserIcon className="h-12 w-12 text-primary" />
                  </div>
                  <h2 className="text-xl font-semibold">{user?.full_name || "Research Agent"}</h2>
                  <p className="text-sm text-muted-foreground mb-4">{user?.email}</p>
                  <div className="flex justify-center gap-2">
                    <Badge variant="secondary" className="bg-primary/10 text-primary border-none">
                      <Shield className="mr-1 h-3 w-3" />
                      Admin
                    </Badge>
                  </div>
                </CardContent>
              </Card>

              <Card className="md:col-span-2 shadow-md bg-card/50">
                <CardHeader>
                  <CardTitle>Account Details</CardTitle>
                  <CardDescription>View and manage your account information</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-muted-foreground uppercase">Email Address</p>
                      <div className="flex items-center gap-2">
                        <Mail className="h-4 w-4 text-primary/60" />
                        <span className="text-sm font-medium">{user?.email}</span>
                      </div>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-muted-foreground uppercase">Full Name</p>
                      <div className="flex items-center gap-2">
                        <UserIcon className="h-4 w-4 text-primary/60" />
                        <span className="text-sm font-medium">{user?.full_name}</span>
                      </div>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-muted-foreground uppercase">Account Status</p>
                      <div className="flex items-center gap-2">
                        <Shield className="h-4 w-4 text-primary/60" />
                        <span className="text-sm font-medium">{user?.disabled ? "Disabled" : "Active"}</span>
                      </div>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-muted-foreground uppercase">Role</p>
                      <Badge variant="outline" className="border-primary/20 text-primary">Sprint 1 Administrator</Badge>
                    </div>
                  </div>

                  <div className="pt-6 border-t border-border">
                    <h3 className="text-sm font-semibold mb-3">Recent Activity</h3>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-xs p-3 bg-muted/30 rounded-lg">
                        <div className="flex items-center gap-3">
                          <Badge variant="outline">Login</Badge>
                          <span>System Login Successful</span>
                        </div>
                        <span className="text-muted-foreground">Just now</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </main>
        <Footer />
      </div>
    </ProtectedRoute>
  )
}
