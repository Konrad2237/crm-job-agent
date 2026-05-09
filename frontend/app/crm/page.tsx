"use client";
import { useState, useEffect, useCallback } from "react";
import { api, Company } from "@/lib/api";
import CRMTable from "@/components/CRMTable";
import ManualEntryModal from "@/components/ManualEntryModal";
import ReplyModal from "@/components/ReplyModal";
import CompanyEditModal from "@/components/CompanyEditModal";

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
  const [showModal, setShowModal] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [replyCompany, setReplyCompany] = useState<Company | null>(null);
  const [replyLoading, setReplyLoading] = useState(false);
  const [editCompany, setEditCompany] = useState<Company | null>(null);
  const [editLoading, setEditLoading] = useState(false);

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

  async function handleManualSubmit(data: {
    name: string;
    url: string;
    what_they_do: string;
    position: string;
    salary_expectation: string;
    contact_email: string;
    notes: string;
  }) {
    setModalLoading(true);
    try {
      await api.addManualCompany({
        name: data.name,
        url: data.url,
        what_they_do: data.what_they_do || undefined,
        position: data.position || undefined,
        salary_expectation: data.salary_expectation || undefined,
        contact_email: data.contact_email || undefined,
        notes: data.notes || undefined,
      });
      setShowModal(false);
      setPage(1);
      fetchPage(1, status);
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
      fetchPage(page, status);
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
      fetchPage(page, status);
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
      fetchPage(page, status);
    } catch (e) {
      setEditLoading(false);
      throw e;
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-2xl font-bold">CRM Dashboard</h1>

        <div className="flex items-center gap-3">
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

          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700"
          >
            + Dodaj ręcznie
          </button>
        </div>
      </div>

      {showModal && (
        <ManualEntryModal
          onSubmit={handleManualSubmit}
          onClose={() => setShowModal(false)}
          loading={modalLoading}
        />
      )}

      {replyCompany && (
        <ReplyModal
          company={replyCompany}
          onSubmit={handleReplySubmit}
          onClose={() => setReplyCompany(null)}
          loading={replyLoading}
        />
      )}

      {editCompany && (
        <CompanyEditModal
          company={editCompany}
          onSubmit={handleEditSubmit}
          onDelete={handleEditDelete}
          onClose={() => setEditCompany(null)}
          loading={editLoading}
        />
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
          onPrev={() => setPage((p) => Math.max(1, p - 1))}
          onNext={() => setPage((p) => p + 1)}
          onReply={setReplyCompany}
          onEdit={setEditCompany}
        />
      )}
    </div>
  );
}
