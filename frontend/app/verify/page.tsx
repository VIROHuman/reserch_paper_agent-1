"use client"

import { useState, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ShieldCheck, Loader2, CheckCircle2 } from "lucide-react"
import api from "@/lib/axios-config"
import { useAuth } from "@/context/auth-context"

function VerifyContent() {
  const [otp, setOtp] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState(false)
  
  const router = useRouter()
  const searchParams = useSearchParams()
  const { login } = useAuth()
  
  const email = searchParams.get("email") || ""
  const type = searchParams.get("type") || "registration" // registration or login

  useEffect(() => {
    if (!email) {
      router.push("/login")
    }
  }, [email, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError("")

    try {
      const endpoint = type === "registration" ? "/verify-registration" : "/token"
      const response = await api.post(endpoint, {
        email,
        otp
      })

      if (type === "registration") {
        setSuccess(true)
        setTimeout(() => {
           router.push("/login")
        }, 3000)
      } else {
        // Login flow
        const { access_token } = response.data
        await login(access_token)
        router.push("/")
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Verification failed. Please check your code.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="w-full max-w-md shadow-xl border-t-4 border-t-primary">
      <CardHeader className="space-y-1 flex flex-col items-center">
        <div className="p-3 bg-primary/10 rounded-full mb-2">
          {success ? <CheckCircle2 className="h-10 w-10 text-green-500" /> : <ShieldCheck className="h-10 w-10 text-primary" />}
        </div>
        <CardTitle className="text-2xl font-bold">Verify Your Identity</CardTitle>
        <CardDescription className="text-center">
          We've sent a 6-digit verification code to <br />
          <span className="font-semibold text-foreground">{email}</span>
        </CardDescription>
      </CardHeader>
      
      {success ? (
        <CardContent className="space-y-4 text-center py-6">
           <p className="text-green-600 font-medium">Account activated successfully!</p>
           <p className="text-sm text-muted-foreground">Redirecting you to login page...</p>
        </CardContent>
      ) : (
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="otp">Verification Code</Label>
              <Input 
                id="otp" 
                placeholder="123456" 
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                className="text-center text-2xl tracking-[10px] font-bold h-14"
                maxLength={6}
                required
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full h-11" disabled={loading || otp.length !== 6}>
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "Verify & Continue"}
            </Button>
            <p className="text-xs text-center text-muted-foreground">
              Didn't receive the code? Check your spam folder or contact support.
            </p>
          </CardFooter>
        </form>
      )}
    </Card>
  )
}

export default function VerifyPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-4 py-12">
      <Suspense fallback={<Loader2 className="h-8 w-8 animate-spin text-primary" />}>
        <VerifyContent />
      </Suspense>
    </div>
  )
}
