"use client";
import { Company } from "@/lib/api";

type Props = {
  company: Company;
  onSkip: () => void;
  onApply: () => void;
  loading: boolean;
};

export default function CompanyCard({ company, onSkip, onApply, loading }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3 max-w-xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">{company.name}</h2>
          <a
            href={company.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:underline break-all"
          >
            {company.domain}
          </a>
        </div>
        <span className="shrink-0 text-xs px-2 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
          {company.status}
        </span>
      </div>

      {company.what_they_do && (
        <p className="text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
          {company.what_they_do}
        </p>
      )}

      <div className="flex gap-3 pt-1">
        <button
          onClick={onSkip}
          disabled={loading}
          className="flex-1 px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Pomiń
        </button>
        <button
          onClick={onApply}
          disabled={loading}
          className="flex-1 px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Wysłałem CV
        </button>
      </div>
    </div>
  );
}
