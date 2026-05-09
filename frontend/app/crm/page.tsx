"use client";
import { useState, useEffect, useCallback } from "react";
import { api, Company } from "@/lib/api";
import CRMTable from "@/components/CRMTable";

const LIMIT = 20;

const STATUS_OPTIONS = [
  { value: "", label: "Wszystkie" },
  { value: "applied", label: "Aplikacje wysłane" },
  { value: "presented", label: "Pokazane" },
  { value: "skipped", label: "Pominięte" },
];

export default function CRMPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback(
    async (p: number, s: string) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getCompanies({ page: p, limit: LIMIT, status: s || undefined });
        setCompanies(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Nieznany błąd");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    fetchPage(page, status);
  }, [page, status, fetchPage]);

  function handleStatusChange(e: React.ChangeEvent<HTMLSelectElement>) {
    setStatus(e.target.value);
    setPage(1);
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-2xl font-bold">CRM Dashboard</h1>

        <select
          value={status}
          onChange={handleStatusChange}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-gray-500 text-sm">Ładowanie...</p>
      ) : (
        <CRMTable
          companies={companies}
          page={page}
          hasMore={companies.length === LIMIT}
          onPrev={() => setPage((p) => Math.max(1, p - 1))}
          onNext={() => setPage((p) => p + 1)}
        />
      )}
    </div>
  );
}
