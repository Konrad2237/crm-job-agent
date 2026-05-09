"use client";
import { useState, useEffect, useCallback } from "react";
import { api, Company } from "@/lib/api";
import CRMTable from "@/components/CRMTable";
import ManualEntryModal from "@/components/ManualEntryModal";
import ReplyModal from "@/components/ReplyModal";
import CompanyEditModal from "@/components/CompanyEditModal";

const LIMIT = 20;

type Stats = { applied: number; skipped: number; presented: number; replied: number };

const PILLS = [
  { value: "", label: "Wszystkie" },
  { value: "applied", label: "Aplikacje", key: "applied" as keyof Stats },
  { value: "skipped", label: "Pominięte", key: "skipped" as keyof Stats },
  { value: "presented", label: "Pokazane", key: "presented" as keyof Stats },
];

export default function CRMPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("created_at");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [replyCompany, setReplyCompany] = useState<Company | null>(null);
  const [replyLoading, setReplyLoading] = useState(false);
  const [editCompany, setEditCompany] = useState<Company | null>(null);
  const [editLoading, setEditLoading] = useState(false);

  const fetchPage = useCallback(async (p: number, s: string, q: string, sortField: string, sortOrder: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCompanies({
        page: p, limit: LIMIT,
        status: s || undefined,
        search: q || undefined,
        sort: sortField,
        order: sortOrder,
      });
      setCompanies(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nieznany błąd");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      setStats(await api.getStats());
    } catch {}
  }, []);

  // debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    fetchPage(page, status, search, sort, order);
  }, [page, status, search, sort, order, fetchPage]);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  function handleSort(field: string) {
    if (sort === field) {
      setOrder(o => o === "desc" ? "asc" : "desc");
    } else {
      setSort(field);
      setOrder("desc");
    }
    setPage(1);
  }

  function handlePillClick(value: string) {
    setStatus(value);
    setPage(1);
  }

  async function handleManualSubmit(data: {
    name: string; url: string; what_they_do: string;
    position: string; salary_expectation: string; contact_email: string; notes: string;
  }) {
    setModalLoading(true);
    try {
      await api.addManualCompany({
        name: data.name, url: data.url,
        what_they_do: data.what_they_do || undefined,
        position: data.position || undefined,
        salary_expectation: data.salary_expectation || undefined,
        contact_email: data.contact_email || undefined,
        notes: data.notes || undefined,
      });
      setShowModal(false);
      fetchStats();
      fetchPage(1, status, search, sort, order);
      setPage(1);
    } catch (e) {
      throw e;
    } finally {
      setModalLoading(false);
    }
  }

  async function handleReplySubmit(data: { reply_status: string; reply_received: string }) {
    if (!replyCompany) return;
    setReplyLoading(true);
    try {
      await api.patchCompany(replyCompany.id, {
        reply_status: data.reply_status || null,
        reply_received: data.reply_received || null,
      });
      setReplyCompany(null);
      fetchStats();
      fetchPage(page, status, search, sort, order);
    } catch (e) {
      throw e;
    } finally {
      setReplyLoading(false);
    }
  }

  async function handleEditSubmit(data: Record<string, string | undefined>) {
    if (!editCompany) return;
    setEditLoading(true);
    try {
      await api.patchCompany(editCompany.id, data);
      setEditCompany(null);
      fetchPage(page, status, search, sort, order);
    } catch (e) {
      throw e;
    } finally {
      setEditLoading(false);
    }
  }

  async function handleEditDelete() {
    if (!editCompany) return;
    setEditLoading(true);
    try {
      await api.deleteCompany(editCompany.id);
      setEditCompany(null);
      fetchStats();
      fetchPage(page, status, search, sort, order);
    } catch (e) {
      setEditLoading(false);
      throw e;
    }
  }

  const replyRate = stats && stats.applied > 0
    ? Math.round((stats.replied / stats.applied) * 100)
    : null;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-2xl font-bold">CRM Dashboard</h1>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700"
        >
          + Dodaj ręcznie
        </button>
      </div>

      {stats && (
        <p className="text-sm text-gray-500">
          {stats.applied} aplikacji · {stats.replied} odpowiedzi
          {replyRate !== null && ` (${replyRate}%)`}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-2 flex-wrap">
          {PILLS.map(pill => {
            const count = pill.key ? stats?.[pill.key] : undefined;
            return (
              <button
                key={pill.value}
                onClick={() => handlePillClick(pill.value)}
                className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                  status === pill.value
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                }`}
              >
                {pill.label}{count !== undefined ? ` (${count})` : ""}
              </button>
            );
          })}
        </div>

        <input
          type="text"
          placeholder="Szukaj nazwy lub domeny..."
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 min-w-[220px]"
        />
      </div>

      {showModal && (
        <ManualEntryModal onSubmit={handleManualSubmit} onClose={() => setShowModal(false)} loading={modalLoading} />
      )}
      {replyCompany && (
        <ReplyModal company={replyCompany} onSubmit={handleReplySubmit} onClose={() => setReplyCompany(null)} loading={replyLoading} />
      )}
      {editCompany && (
        <CompanyEditModal company={editCompany} onSubmit={handleEditSubmit} onDelete={handleEditDelete} onClose={() => setEditCompany(null)} loading={editLoading} />
      )}

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
          onPrev={() => setPage(p => Math.max(1, p - 1))}
          onNext={() => setPage(p => p + 1)}
          onReply={setReplyCompany}
          onEdit={setEditCompany}
          sort={sort}
          order={order}
          onSort={handleSort}
        />
      )}
    </div>
  );
}
