import React, { useEffect, useState } from 'react';
import {
  BookOpen,
  Upload,
  Plus,
  Trash2,
  Search,
  FileText,
  HelpCircle,
  CheckCircle,
  Clock,
  AlertCircle,
  Database,
  Sparkles,
} from 'lucide-react';
import { api } from '../lib/api';
import type { Document } from '../types';

export const KnowledgeBase: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showFaqModal, setShowFaqModal] = useState(false);

  // Upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docTitle, setDocTitle] = useState('');
  const [uploading, setUploading] = useState(false);

  // FAQ state
  const [faqTitle, setFaqTitle] = useState('');
  const [faqs, setFaqs] = useState<{ question: string; answer: string; category: string }[]>([
    { question: '', answer: '', category: 'General' },
  ]);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<{
    document_title: string;
    content: string;
    similarity_score: number;
  }[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const res = await api.listDocuments();
      setDocuments(res.items);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setUploading(true);
    try {
      await api.uploadDocument(selectedFile, docTitle || undefined);
      setShowUploadModal(false);
      setSelectedFile(null);
      setDocTitle('');
      await fetchDocuments();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleCreateFAQ = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!faqTitle || faqs.length === 0 || !faqs[0].question) return;

    setUploading(true);
    try {
      await api.createFAQ({
        title: faqTitle,
        items: faqs.filter((f) => f.question && f.answer),
      });
      setShowFaqModal(false);
      setFaqTitle('');
      setFaqs([{ question: '', answer: '', category: 'General' }]);
      await fetchDocuments();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'FAQ creation failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this knowledge document?')) return;
    try {
      await api.deleteDocument(id);
      await fetchDocuments();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearching(true);
    try {
      const res = await api.searchKnowledge(searchQuery, 3);
      setSearchResults(res.results);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-2">
            Knowledge Base & RAG <Database className="w-5 h-5 text-indigo-400" />
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Vector embeddings stored with pgvector. The voice agent searches these documents in real time to answer customer questions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFaqModal(true)}
            className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer"
          >
            <Plus className="w-4 h-4" /> Add FAQs
          </button>
          <button
            onClick={() => setShowUploadModal(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer shadow-lg shadow-blue-600/25"
          >
            <Upload className="w-4 h-4" /> Upload Document
          </button>
        </div>
      </div>

      {/* Semantic Vector Search Test Bar */}
      <div className="glass rounded-xl p-5 border border-slate-800 shadow space-y-3">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
          <Search className="w-4 h-4 text-blue-400" />
          Test pgvector Semantic Search
        </h3>
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Ask anything (e.g. 'What is your root canal price?' or 'Where can I park?')..."
            className="flex-1 px-4 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            disabled={searching}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            {searching ? 'Searching...' : 'Search'}
          </button>
        </form>

        {searchResults.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-slate-800/80">
            <span className="text-[11px] font-semibold text-slate-400">Retrieved Chunks:</span>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {searchResults.map((r, i) => (
                <div key={i} className="bg-slate-900/80 border border-slate-800 p-3 rounded-xl text-xs space-y-1.5">
                  <div className="flex items-center justify-between text-[10px] text-slate-400">
                    <span className="font-bold text-blue-400 truncate max-w-[150px]">{r.document_title}</span>
                    <span className="text-emerald-400 font-mono font-bold">
                      {Math.round(r.similarity_score * 100)}% match
                    </span>
                  </div>
                  <p className="text-slate-300 text-[11px] line-clamp-3">{r.content}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Documents Table */}
      <div className="glass rounded-xl border border-slate-800 shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="text-sm font-bold text-white">Ingested Documents & FAQs</h2>
          <span className="text-xs text-slate-400">{documents.length} Total</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/60 text-slate-400 border-b border-slate-800 uppercase font-semibold text-[10px] tracking-wider">
              <tr>
                <th className="px-6 py-3">Document Title</th>
                <th className="px-6 py-3">Type</th>
                <th className="px-6 py-3">Chunks</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Uploaded</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {documents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                    No documents uploaded yet. Click "Upload Document" or "Add FAQs" to get started.
                  </td>
                </tr>
              ) : (
                documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-900/40 transition">
                    <td className="px-6 py-4 font-semibold text-white flex items-center gap-2">
                      {doc.file_type === 'faq' ? (
                        <HelpCircle className="w-4 h-4 text-indigo-400 shrink-0" />
                      ) : (
                        <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                      )}
                      <span>{doc.title}</span>
                    </td>
                    <td className="px-6 py-4 uppercase text-slate-400 font-mono text-[10px]">{doc.file_type}</td>
                    <td className="px-6 py-4 text-slate-300 font-mono">{doc.chunk_count}</td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          doc.status === 'READY'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : doc.status === 'PROCESSING'
                            ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
                            : 'bg-red-500/10 text-red-400 border border-red-500/20'
                        }`}
                      >
                        {doc.status === 'READY' && <CheckCircle className="w-3 h-3" />}
                        {doc.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-400">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition cursor-pointer"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Upload Document Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass rounded-2xl p-6 border border-slate-800 max-w-md w-full shadow-2xl space-y-4">
            <h2 className="text-base font-bold text-white">Upload Knowledge Document</h2>
            <form onSubmit={handleUpload} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Document Title</label>
                <input
                  type="text"
                  value={docTitle}
                  onChange={(e) => setDocTitle(e.target.value)}
                  placeholder="e.g. Dental Treatment & Pricing Policy"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Select File (PDF, DOCX, TXT)</label>
                <input
                  type="file"
                  required
                  accept=".pdf,.docx,.txt"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-600/25"
                >
                  {uploading ? 'Processing & Chunking...' : 'Upload & Embed'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* FAQ Creation Modal */}
      {showFaqModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass rounded-2xl p-6 border border-slate-800 max-w-xl w-full shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            <h2 className="text-base font-bold text-white">Add Structured FAQ Set</h2>
            <form onSubmit={handleCreateFAQ} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">FAQ Set Title</label>
                <input
                  type="text"
                  required
                  value={faqTitle}
                  onChange={(e) => setFaqTitle(e.target.value)}
                  placeholder="e.g. Clinic Visiting Hours & Policies"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
                />
              </div>

              <div className="space-y-3">
                <label className="block text-xs font-semibold text-slate-300">Question & Answer Pairs</label>
                {faqs.map((faq, index) => (
                  <div key={index} className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl space-y-2">
                    <input
                      type="text"
                      placeholder="Question: What are your working hours?"
                      value={faq.question}
                      onChange={(e) => {
                        const updated = [...faqs];
                        updated[index].question = e.target.value;
                        setFaqs(updated);
                      }}
                      className="w-full px-3 py-1.5 bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-white"
                    />
                    <textarea
                      placeholder="Answer: We are open Monday to Saturday from 9 AM to 7 PM."
                      rows={2}
                      value={faq.answer}
                      onChange={(e) => {
                        const updated = [...faqs];
                        updated[index].answer = e.target.value;
                        setFaqs(updated);
                      }}
                      className="w-full px-3 py-1.5 bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-white"
                    />
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setFaqs([...faqs, { question: '', answer: '', category: 'General' }])}
                  className="text-xs text-blue-400 hover:text-blue-300 font-semibold"
                >
                  + Add Another FAQ Item
                </button>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowFaqModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold"
                >
                  {uploading ? 'Embedding FAQs...' : 'Save & Embed FAQs'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
