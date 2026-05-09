"use client";
import { useState } from "react";
import { Company } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  presented: "Pokazana",
  skipped: "Pominięta",
  applied: "Aplikacja wysłana",
};

const STATUS_STYLES: Record<string, string> = {
  presented: "bg-blue-50 text-blue-700 border-blue-200",
  skipped: "bg-gray-100 text-gray-700 border-gray-300",
  applied: "bg-green-50 text-green-700 border-green-200",
};

const REPLY_LABELS: Record<string, string> = {
  rejected: "Odrzucono",
  interview: "Rozmowa",
  offer: "Oferta",
};

const REPLY_STYLES: Record<string, string> = {
  rejected: "bg-red-50 text-red-700 border-red-200",
  interview: "bg-blue-50 text-blue-700 border-blue-200",
  offer: "bg-green-50 text-green-700 border-green-200",
};

type Props = {
  companies: Company[];
  page: number;
  hasMore: boolean;
  onPrev: () => void;
  onNext: () => void;
  onReply?: (company: Company) => void;
  onEdit?: (company: Company) => void;
  sort?: string;
  order?: "asc" | "desc";
  onSort?: (field: string) => void;
};

function SortHeader({ field, label, sort, order, onSort }: {
  field: string; label: string; sort?: string; order?: "asc" | "desc"; onSort?: (f: string) => void;
}) {
  const active = sort === field;
  return (
    <button
      onClick={() => onSort?.(field)}
      className="flex items-center gap-1 hover:text-gray-900 font-medium transition-colors"
    >
      {label}
      <span className={`text-xs ${active ? "text-blue-600" : "text-gray-400"}`}>
        {active ? (order === "asc" ? "↑" : "↓") : "↕"}
      </span>
    </button>
  );
}

export default function CRMTable({ companies, page, hasMore, onPrev, onNext, onReply, onEdit, sort, order, onSort }: Props) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  function copyEmail(id: string, email: string) {
    navigator.clipboard.writeText(email).catch(() => {
      const el = document.createElement("textarea");
      el.value = email;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
    });
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  }

  if (companies.length === 0) {
    return <p className="text-gray-600 text-sm py-8 text-center">Brak firm do wyświetlenia.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 text-left text-gray-700">
              <th className="px-4 py-3">
                <SortHeader field="name" label="Firma" sort={sort} order={order} onSort={onSort} />
              </th>
              <th className="px-4 py-3 font-medium">Czym się zajmuje</th>
              <th className="px-4 py-3">
                <SortHeader field="status" label="Status" sort={sort} order={order} onSort={onSort} />
              </th>
              <th className="px-4 py-3 font-medium">Odpowiedź</th>
              <th className="px-4 py-3 font-medium">Stanowisko</th>
              <th className="px-4 py-3 font-medium">Wynagrodzenie</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Notatki</th>
              <th className="px-4 py-3">
                <SortHeader field="created_at" label="Data" sort={sort} order={order} onSort={onSort} />
              </th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {companies.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3">
                  <div className="font-semibold text-gray-900">{c.name}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:underline"
                    >
                      {c.domain}
                    </a>
                    <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${
                      c.source === "manual"
                        ? "bg-purple-50 text-purple-700 border-purple-200"
                        : "bg-gray-100 text-gray-600 border-gray-200"
                    }`}>
                      {c.source === "manual" ? "ręcznie" : "agent"}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-700 max-w-xs truncate">
                  {c.what_they_do ?? <span className="text-gray-400">—</span>}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-1 rounded-full border font-medium ${
                    STATUS_STYLES[c.status] ?? "bg-gray-100 text-gray-700 border-gray-300"
                  }`}>
                    {STATUS_LABELS[c.status] ?? c.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {c.status === "applied" ? (
                    <div className="flex flex-col gap-1">
                      {c.reply_status ? (
                        <>
                          <span className={`text-xs px-2 py-1 rounded-full border w-fit font-medium ${
                            REPLY_STYLES[c.reply_status] ?? "bg-gray-100 text-gray-700 border-gray-300"
                          }`}>
                            {REPLY_LABELS[c.reply_status] ?? c.reply_status}
                          </span>
                          {c.reply_received && (
                            <span className="text-xs text-gray-600">{c.reply_received}</span>
                          )}
                          {onReply && (
                            <button onClick={() => onReply(c)} className="text-xs text-blue-600 hover:underline text-left w-fit">
                              Edytuj
                            </button>
                          )}
                        </>
                      ) : (
                        onReply && (
                          <button onClick={() => onReply(c)} className="text-xs text-gray-500 hover:text-blue-600 hover:underline text-left">
                            + Ustaw odpowiedź
                          </button>
                        )
                      )}
                    </div>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-700">{c.position ?? <span className="text-gray-400">—</span>}</td>
                <td className="px-4 py-3 text-gray-700">{c.salary_expectation ?? <span className="text-gray-400">—</span>}</td>
                <td className="px-4 py-3 text-gray-700">
                  {c.contact_email ? (
                    <div className="flex items-center gap-2">
                      <span>{c.contact_email}</span>
                      <button
                        onClick={() => copyEmail(c.id, c.contact_email!)}
                        className={`text-xs px-2 py-0.5 rounded border transition-colors whitespace-nowrap ${
                          copiedId === c.id
                            ? "bg-green-50 text-green-700 border-green-200"
                            : "bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200"
                        }`}
                      >
                        {copiedId === c.id ? "✓ Skopiowano" : "Kopiuj"}
                      </button>
                    </div>
                  ) : <span className="text-gray-400">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-700 max-w-xs truncate" title={c.notes ?? ""}>
                  {c.notes ?? <span className="text-gray-400">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {new Date(c.applied_at ?? c.created_at).toLocaleDateString("pl-PL")}
                </td>
                <td className="px-4 py-3">
                  {onEdit && (
                    <button
                      onClick={() => onEdit(c)}
                      className="text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-100 hover:text-gray-900 whitespace-nowrap transition-colors"
                    >
                      Edytuj
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-gray-700">
        <button
          onClick={onPrev}
          disabled={page === 1}
          className="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed font-medium"
        >
          ← Poprzednia
        </button>
        <span className="text-gray-500">Strona {page}</span>
        <button
          onClick={onNext}
          disabled={!hasMore}
          className="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed font-medium"
        >
          Następna →
        </button>
      </div>
    </div>
  );
}
