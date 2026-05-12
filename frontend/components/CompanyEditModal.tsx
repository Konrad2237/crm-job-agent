"use client";
import { useState } from "react";
import { Company } from "@/lib/api";

const STATUS_OPTIONS = [
  { value: "skipped", label: "Pominięta" },
  { value: "applied", label: "Aplikacja wysłana" },
  { value: "presented", label: "Pokazana" },
];

type FormData = {
  name: string;
  what_they_do: string;
  status: string;
  position: string;
  salary_expectation: string;
  contact_email: string;
  notes: string;
};

type Props = {
  company: Company;
  onSubmit: (data: Partial<FormData>) => Promise<void>;
  onDelete: () => Promise<void>;
  onClose: () => void;
  loading: boolean;
};

export default function CompanyEditModal({ company, onSubmit, onDelete, onClose, loading }: Props) {
  const [form, setForm] = useState<FormData>({
    name: company.name ?? "",
    what_they_do: company.what_they_do ?? "",
    status: company.status ?? "skipped",
    position: company.position ?? "",
    salary_expectation: company.salary_expectation ?? "",
    contact_email: company.contact_email ?? "",
    notes: company.notes ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const set =
    (field: keyof FormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));

  async function handleSubmit() {
    if (!form.name.trim()) {
      setError("Nazwa jest wymagana.");
      return;
    }
    setError(null);
    try {
      await onSubmit({
        name: form.name || undefined,
        what_they_do: form.what_they_do || undefined,
        status: form.status,
        position: form.position || undefined,
        salary_expectation: form.salary_expectation || undefined,
        contact_email: form.contact_email || undefined,
        notes: form.notes || undefined,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nieznany błąd.");
    }
  }

  async function handleDelete() {
    setError(null);
    try {
      await onDelete();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nieznany błąd.");
      setConfirmDelete(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl space-y-5 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Edytuj firmę</h2>
            <a
              href={company.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-blue-600 hover:underline"
            >
              {company.domain}
            </a>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="text-gray-400 hover:text-gray-600 disabled:opacity-50 text-xl leading-none"
          >
            ✕
          </button>
        </div>

        {error && (
          <p className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block sm:col-span-2">
            <span className="text-sm text-gray-900 font-medium">Nazwa firmy</span>
            <input
              type="text"
              value={form.name}
              onChange={set("name")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>

          <label className="block sm:col-span-2">
            <span className="text-sm text-gray-900 font-medium">Czym się zajmuje</span>
            <input
              type="text"
              value={form.what_they_do}
              onChange={set("what_they_do")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>

          <label className="block">
            <span className="text-sm text-gray-900 font-medium">Status</span>
            <select
              value={form.status}
              onChange={set("status")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm text-gray-900 font-medium">Stanowisko</span>
            <input
              type="text"
              placeholder="np. AI Engineer"
              value={form.position}
              onChange={set("position")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>

          <label className="block">
            <span className="text-sm text-gray-900 font-medium">Oczekiwania finansowe</span>
            <input
              type="text"
              placeholder="np. 15 000 PLN netto"
              value={form.salary_expectation}
              onChange={set("salary_expectation")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>

          <label className="block">
            <span className="text-sm text-gray-900 font-medium">E-mail kontaktowy</span>
            <input
              type="email"
              placeholder="np. hr@firma.pl"
              value={form.contact_email}
              onChange={set("contact_email")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>

          <label className="block sm:col-span-2">
            <span className="text-sm text-gray-900 font-medium">Notatki</span>
            <textarea
              rows={3}
              value={form.notes}
              onChange={set("notes")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
            />
          </label>
        </div>

        <div className="flex items-center justify-between pt-1">
          {confirmDelete ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-red-600">Na pewno usunąć?</span>
              <button
                onClick={handleDelete}
                disabled={loading}
                className="px-3 py-1.5 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                Tak, usuń
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                disabled={loading}
                className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
              >
                Anuluj
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              disabled={loading}
              className="text-sm text-red-500 hover:text-red-700 disabled:opacity-50"
            >
              Usuń firmę
            </button>
          )}

          <div className="flex gap-3">
            <button
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
            >
              Anuluj
            </button>
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Zapisuję..." : "Zapisz"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
