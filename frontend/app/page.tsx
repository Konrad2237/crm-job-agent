"use client";
import { useState } from "react";
import { api, Company } from "@/lib/api";
import CompanyCard from "@/components/CompanyCard";
import ApplicationForm from "@/components/ApplicationForm";

type Phase = "idle" | "found" | "applying";

export default function DiscoveryPage() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [company, setCompany] = useState<Company | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function findCompany() {
    setLoading(true);
    setError(null);
    try {
      const c = await api.findCompany();
      setCompany(c);
      setPhase("found");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nieznany błąd");
    } finally {
      setLoading(false);
    }
  }

  async function handleSkip() {
    if (!company) return;
    setLoading(true);
    setError(null);
    try {
      await api.skipCompany(company.id);
      setCompany(null);
      setPhase("idle");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nieznany błąd");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(data: {
    position: string;
    salary_expectation: string;
    contact_email: string;
    notes: string;
  }) {
    if (!company) return;
    setLoading(true);
    setError(null);
    try {
      await api.applyCompany(company.id, data);
      setCompany(null);
      setPhase("idle");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nieznany błąd");
      setPhase("found");
    } finally {
      setLoading(false);
    }
  }

  async function handleApply(data: {
    position: string;
    salary_expectation: string;
    contact_email: string;
    notes: string;
  }) {
    if (!company) return;
    setLoading(true);
    setError(null);
    try {
      await api.applyCompany(company.id, data);
      setCompany(null);
      setPhase("idle");
      const next = await api.findCompany();
      setCompany(next);
      setPhase("found");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nieznany błąd");
      setPhase("found");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Znajdź firmę</h1>
        <p className="text-gray-500 text-sm mt-1">
          Agent wyszukuje polskie firmy działające w obszarze AI.
        </p>
      </div>

      <button
        onClick={findCompany}
        disabled={loading}
        className="px-5 py-2.5 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? "Szukam..." : "Znajdź firmę"}
      </button>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {company && phase !== "idle" && (
        <div className="space-y-3">
          <CompanyCard
            company={company}
            onSkip={handleSkip}
            onApply={() => setPhase("applying")}
            loading={loading}
          />

          {phase === "applying" && (
            <ApplicationForm
              onSubmit={handleApply}
              onSave={handleSave}
              onCancel={() => setPhase("found")}
              loading={loading}
            />
          )}
        </div>
      )}
    </div>
  );
}
