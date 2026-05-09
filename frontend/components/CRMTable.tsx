"use client";
import { Company } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  presented: "Pokazana",
  skipped: "Pominięta",
  applied: "Aplikacja wysłana",
};

const STATUS_STYLES: Record<string, string> = {
  presented: "bg-blue-50 text-blue-700 border-blue-200",
  skipped: "bg-gray-100 text-gray-600 border-gray-200",
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
};

export default function CRMTable({ companies, page, hasMore, onPrev, onNext, onReply, onEdit }: Props) {
  if (companies.length === 0) {
    return <p className="text-gray-500 text-sm">Brak firm do wyświetlenia.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 text-left">
              <th className="px-4 py-3 font-medium text-gray-600">Firma</th>
              <th className="px-4 py-3 font-medium text-gray-600">Czym się zajmuje</th>
              <th className="px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="px-4 py-3 font-medium text-gray-600">Odpowiedź</th>
              <th className="px-4 py-3 font-medium text-gray-600">Stanowisko</th>
              <th className="px-4 py-3 font-medium text-gray-600">Data</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {companies.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <div className="font-medium">{c.name}</div>
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 hover:underline"
                  >
                    {c.domain}
                  </a>
                </td>
                <td className="px-4 py-3 text-gray-600 max-w-xs truncate">
                  {c.what_they_do ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`text-xs px-2 py-1 rounded-full border ${
                      STATUS_STYLES[c.status] ?? "bg-gray-100 text-gray-600 border-gray-200"
                    }`}
                  >
                    {STATUS_LABELS[c.status] ?? c.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {c.status === "applied" ? (
                    <div className="flex flex-col gap-1">
                      {c.reply_status ? (
                        <>
                          <span
                            className={`text-xs px-2 py-1 rounded-full border w-fit ${
                              REPLY_STYLES[c.reply_status] ?? "bg-gray-100 text-gray-600 border-gray-200"
                            }`}
                          >
                            {REPLY_LABELS[c.reply_status] ?? c.reply_status}
                          </span>
                          {c.reply_received && (
                            <span className="text-xs text-gray-400">{c.reply_received}</span>
                          )}
                          {onReply && (
                            <button
                              onClick={() => onReply(c)}
                              className="text-xs text-blue-500 hover:underline text-left w-fit"
                            >
                              Edytuj
                            </button>
                          )}
                        </>
                      ) : (
                        onReply && (
                          <button
                            onClick={() => onReply(c)}
                            className="text-xs text-gray-400 hover:text-blue-600 hover:underline text-left"
                          >
                            + Ustaw odpowiedź
                          </button>
                        )
                      )}
                    </div>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-600">{c.position ?? "—"}</td>
                <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                  {new Date(c.applied_at ?? c.created_at).toLocaleDateString("pl-PL")}
                </td>
                <td className="px-4 py-3">
                  {onEdit && (
                    <button
                      onClick={() => onEdit(c)}
                      className="text-xs text-gray-400 hover:text-blue-600 hover:underline whitespace-nowrap"
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

      <div className="flex items-center justify-between text-sm">
        <button
          onClick={onPrev}
          disabled={page === 1}
          className="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Poprzednia
        </button>
        <span className="text-gray-500">Strona {page}</span>
        <button
          onClick={onNext}
          disabled={!hasMore}
          className="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Następna
        </button>
      </div>
    </div>
  );
}
