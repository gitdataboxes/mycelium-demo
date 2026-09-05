"use client";

import { api } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function VerifyContent() {
  const params = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setError("No token provided");
      return;
    }

    api.auth
      .verify(token)
      .then(() => {
        router.push("/");
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Verification failed");
      });
  }, [params, router]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <h1 className="text-2xl font-bold text-red-600">Login failed</h1>
        <p className="text-gray-600">{error}</p>
        <a href="/auth" className="text-gray-900 underline">
          Try again
        </a>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen">
      <p className="text-gray-500">Verifying your login link...</p>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen">
          <p className="text-gray-500">Loading...</p>
        </div>
      }
    >
      <VerifyContent />
    </Suspense>
  );
}
