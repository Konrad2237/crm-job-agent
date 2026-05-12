"use client";
import { useState } from "react";
import { Company } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  presented: "Pokazana",
  skipped: "Pominięta",
  applied: "Aplikacja",
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

function ExpandableText({ text, limit = 45 }: { text: string | null | undefined; limit?: number }) {
  const [expanded, setExpanded] = useState(false);
  if (!text) return <span className="text-gray-400">—</span>;
  if (text.length <= limit) return <span>{text}</span>;
  return (
    <span>
      {expanded ? text : text.slice(0, limit) + "…"}
      {" "}
      <button
        onClick={e => { e.stopPropagation(); setExpanded(v => !v); }}
        className="text-blue-500 hover:underline whitespace-nowrap"
      >
        {expanded ? "zwiń" : "więcej"}
      </button>
    </span>
  );
}

function shortDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit" });
}

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
      className="flex items-center gap-0.5 hover:text-gray-900 font-medium transition-colors whitespace-nowrap"
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

  const th = "px-2 py-2 text-xs font-medium text-gray-600 whitespace-nowrap";
  const td = "px-2 py-2 text-xs text-gray-700 align-top";

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 text-left text-gray-600">
              <th className={th}><SortHeader field="name" label="Firma" sort={sort} order={order} onSort={onSort} /></th>
              <th className={th}>Czym się zajmuje</th>
              <th className={th}><SortHeader field="status" label="Status" sort={sort} order={order} onSort={onSort} /></th>
              <th className={th}>Odpow.</th>
              <th className={th}>Stanowisko</th>
              <th className={th}>Wynagr.</th>
              <th className={th}>Email</th>
              <th className={th}>Notatki</th>
              <th className={th}><SortHeader field="created_at" label="Data" sort={sort} order={order} onSort={onSort} /></th>
              <th className={th}></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {companies.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                <td className={td}>
                  <div className="font-semibold text-gray-900 text-xs">{c.name}</div>
                  <div className="flex items-center gap-1 mt-0.5 flex-wrap">
                    {c.url ? (
                      <a href={c.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                        {c.domain}
                      </a>
                    ) : (
                      <span className="text-gray-400">{c.domain ?? "—"}</span>
                    )}
                    <span className={`px-1 py-0.5 rounded border font-medium ${
                      c.source === "manual"
                        ? "bg-purple-50 text-purple-700 border-purple-200"
                        : "bg-gray-100 text-gray-600 border-gray-200"
                    }`}>
                      {c.source === "manual" ? "ręcznie" : "agent"}
                    </span>
                  </div>
                </td>
                <td className={`${td} max-w-[140px]`}>
                  <ExpandableText text={c.what_they_do} />
                </td>
                <td className={td}>
                  <span className={`px-1.5 py-0.5 rounded-full border font-medium whitespace-nowrap ${
                    STATUS_STYLES[c.status] ?? "bg-gray-100 text-gray-700 border-gray-300"
                  }`}>
                    {STATUS_LABELS[c.status] ?? c.status}
                  </span>
                </td>
                <td className={td}>
                  {c.status === "applied" ? (
                    <div className="flex flex-col gap-0.5">
                      {c.reply_status ? (
                        <>
                          <span className={`px-1.5 py-0.5 rounded-full border w-fit font-medium whitespace-nowrap ${
                            REPLY_STYLES[c.reply_status] ?? "bg-gray-100 text-gray-700 border-gray-300"
                          }`}>
                            {REPLY_LABELS[c.reply_status] ?? c.reply_status}
                          </span>
                          {c.reply_received && (
                            <span className="text-gray-500">{c.reply_received}</span>
                          )}
                          {onReply && (
                            <button onClick={() => onReply(c)} className="text-blue-600 hover:underline text-left w-fit">
                              Edytuj
                            </button>
                          )}
                        </>
                      ) : (
                        onReply && (
                          <button onClick={() => onReply(c)} className="text-gray-500 hover:text-blue-600 hover:underline text-left whitespace-nowrap">
                            + Ustaw
                          </button>
                        )
                      )}
                    </div>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </td>
                <td className={td}>{c.position ?? <span className="text-gray-400">—</span>}</td>
                <td className={td}>{c.salary_expectation ?? <span className="text-gray-400">—</span>}</td>
                <td className={`${td} max-w-[130px]`}>
                  {c.contact_email ? (
                    <div className="flex items-center gap-1">
                      <span className="truncate max-w-[80px]" title={c.contact_email}>{c.contact_email}</span>
                      <button
                        onClick={() => copyEmail(c.id, c.contact_email!)}
                        className={`shrink-0 px-1 py-0.5 rounded border transition-colors whitespace-nowrap ${
                          copiedId === c.id
                            ? "bg-green-50 text-green-700 border-green-200"
                            : "bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200"
                        }`}
                      >
                        {copiedId === c.id ? "✓" : "Kopiuj"}
                      </button>
                    </div>
                  ) : <span className="text-gray-400">—</span>}
                </td>
                <td className={`${td} max-w-[150px]`}>
                  <ExpandableText text={c.notes} />
                </td>
                <td className={`${td} whitespace-nowrap`}>
                  {shortDate(c.applied_at ?? c.created_at)}
                </td>
                <td className={td}>
                  {onEdit && (
                    <button
                      onClick={() => onEdit(c)}
                      className="px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-100 hover:text-gray-900 whitespace-nowrap transition-colors"
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
