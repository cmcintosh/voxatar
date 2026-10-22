import { useState, useEffect, useCallback } from "react";
import { Upload, Trash2, FileText, AlertCircle } from "lucide-react";
import { format, parseISO } from "date-fns";
import type { KnowledgeDocument } from "../types";

export default function KnowledgeBase() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const fetchDocuments = useCallback(() => {
    fetch("/api/knowledge/documents")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch documents");
        return res.json();
      })
      .then((data) => setDocuments(data.documents ?? []))
      .catch((err) => {
        console.error("Knowledge fetch error:", err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleUpload = useCallback(
    async (files: FileList) => {
      setUploading(true);
      setError(null);
      try {
        for (const file of Array.from(files)) {
          const formData = new FormData();
          formData.append("file", file);
          const res = await fetch("/api/knowledge/upload", {
            method: "POST",
            body: formData,
          });
          if (!res.ok) throw new Error(`Upload failed for ${file.name}`);
        }
        fetchDocuments();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        setError(msg);
      } finally {
        setUploading(false);
      }
    },
    [fetchDocuments]
  );

  const handleDelete = useCallback(
    async (docId: string) => {
      try {
        const res = await fetch(`/api/knowledge/documents/${docId}`, {
          method: "DELETE",
        });
        if (!res.ok) throw new Error("Delete failed");
        fetchDocuments();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Delete failed";
        setError(msg);
      }
    },
    [fetchDocuments]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (e.dataTransfer.files.length > 0) {
        handleUpload(e.dataTransfer.files);
      }
    },
    [handleUpload]
  );

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">Knowledge Base</h1>

      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-300 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div>
            <p>{error}</p>
            <button
              onClick={() => setError(null)}
              className="text-sm text-red-400 hover:text-red-300 mt-1"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Upload zone */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        className={`dark-card rounded-xl border-2 border-dashed p-8 text-center transition-colors cursor-pointer ${
          dragOver
            ? "border-indigo-500 bg-indigo-500/10"
            : "border-slate-600 hover:border-slate-500"
        }`}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <Upload
          className={`w-10 h-10 mx-auto mb-3 ${
            dragOver ? "text-indigo-400" : "text-slate-500"
          }`}
        />
        <p className="text-slate-300 font-medium">
          {uploading ? "Uploading..." : "Drag and drop files here"}
        </p>
        <p className="text-sm text-slate-500 mt-1">
          or click to browse · PDF, TXT, MD, DOCX
        </p>
        <input
          id="file-input"
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              handleUpload(e.target.files);
            }
          }}
        />
      </div>

      {/* Document list */}
      <div className="dark-card rounded-xl border overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-700">
          <h2 className="text-lg font-semibold text-slate-100">Documents</h2>
        </div>
        {loading ? (
          <div className="px-6 py-12 text-center text-slate-400">
            Loading documents...
          </div>
        ) : documents.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-400">
            <FileText className="w-8 h-8 mx-auto mb-3 opacity-50" />
            <p>No documents uploaded yet.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-slate-400 text-left">
                <th className="px-6 py-3 font-medium">Filename</th>
                <th className="px-6 py-3 font-medium">Size</th>
                <th className="px-6 py-3 font-medium">Uploaded</th>
                <th className="px-6 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr
                  key={doc.id}
                  className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors"
                >
                  <td className="px-6 py-3 text-slate-300 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-slate-500" />
                    {doc.filename}
                  </td>
                  <td className="px-6 py-3 text-slate-400">
                    {formatSize(doc.size_bytes)}
                  </td>
                  <td className="px-6 py-3 text-slate-400">
                    {format(parseISO(doc.uploaded_at), "MMM d, yyyy")}
                  </td>
                  <td className="px-6 py-3">
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="text-red-400 hover:text-red-300 p-1 rounded transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}