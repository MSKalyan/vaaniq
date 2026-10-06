"use client";

import { useState } from "react";
import { Library, Plus } from "lucide-react";

import { DashboardLayout } from "@/components/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import {
  useCreateKnowledgeBase,
  useCreateKnowledgeDocument,
  useDeleteKnowledgeBase,
  useDeleteKnowledgeDocument,
  useKnowledgeBases,
  useKnowledgeDocuments,
  useKnowledgeSearch,
} from "@/hooks/use-knowledge";

export default function KnowledgePage() {
  const bases = useKnowledgeBases();
  const [selected, setSelected] = useState<string | null>(null);
  const documents = useKnowledgeDocuments(selected);

  const [baseName, setBaseName] = useState("");
  const createBase = useCreateKnowledgeBase();

  const [docTitle, setDocTitle] = useState("");
  const [docContent, setDocContent] = useState("");
  const createDocument = useCreateKnowledgeDocument();

  const deleteBase = useDeleteKnowledgeBase();
  const deleteDocument = useDeleteKnowledgeDocument();

  const [searchQuery, setSearchQuery] = useState("");
  const search = useKnowledgeSearch(searchQuery, selected ? [selected] : []);

  const activeBaseId = selected ?? bases.data?.[0]?.id ?? null;

  return (
    <DashboardLayout>
      <h1 className="mb-6 text-2xl font-semibold">Knowledge Base</h1>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Bases</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {bases.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : bases.isError ? (
              <p className="text-sm text-destructive">Unable to load knowledge bases.</p>
            ) : bases.data?.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No knowledge bases yet. Create one to give agents grounding context.
              </p>
            ) : (
              <ul className="flex flex-col gap-1">
                {(bases.data ?? []).map((base) => (
                  <li key={base.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(base.id)}
                      className={
                        base.id === activeBaseId
                          ? "w-full rounded-md bg-primary px-3 py-2 text-left text-sm text-primary-foreground"
                          : "w-full rounded-md px-3 py-2 text-left text-sm hover:bg-secondary"
                      }
                    >
                      {base.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <div className="border-t pt-4">
              <Label htmlFor="base-name">New base</Label>
              <Input
                id="base-name"
                value={baseName}
                placeholder="Sales playbooks"
                onChange={(event) => setBaseName(event.target.value)}
              />
              <Button
                className="mt-2"
                size="sm"
                disabled={!baseName.trim() || createBase.isPending}
                onClick={() =>
                  createBase.mutate(
                    { name: baseName.trim() },
                    { onSuccess: (created) => {
                      setBaseName("");
                      setSelected(created.id);
                    } }
                  )
                }
              >
                <Plus className="h-4 w-4" /> Add base
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Documents</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {!activeBaseId ? (
              <p className="text-sm text-muted-foreground">Select or create a base first.</p>
            ) : (
              <>
                {documents.isLoading ? (
                  <p className="text-sm text-muted-foreground">Loading documents…</p>
                ) : documents.data?.length === 0 ? (
                  <p className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Library className="h-4 w-4" /> No documents in this base yet.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {documents.data?.map((document) => (
                      <li
                        key={document.id}
                        className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                      >
                        <span>{document.title}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-muted-foreground">
                            {document.source_type}
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive"
                            onClick={() => deleteDocument.mutate(document.id)}
                          >
                            Delete
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}

                <div className="flex flex-col gap-2 border-t pt-4">
                  <Label htmlFor="doc-title">Add document</Label>
                  <Input
                    id="doc-title"
                    value={docTitle}
                    placeholder="Pricing FAQ"
                    onChange={(event) => setDocTitle(event.target.value)}
                  />
                  <Textarea
                    rows={5}
                    value={docContent}
                    placeholder="Paste the text the agent should be able to answer from…"
                    onChange={(event) => setDocContent(event.target.value)}
                  />
                  <Button
                    size="sm"
                    disabled={
                      !docTitle.trim() || !docContent.trim() || createDocument.isPending
                    }
                    onClick={() =>
                      createDocument.mutate(
                        {
                          knowledge_base_id: activeBaseId,
                          title: docTitle.trim(),
                          content: docContent.trim(),
                        },
                        {
                          onSuccess: () => {
                            setDocTitle("");
                            setDocContent("");
                          },
                        }
                      )
                    }
                  >
                    Index document
                  </Button>
                  {(createDocument.isError || deleteDocument.isError) && (
                    <p className="text-sm text-destructive">
                      {(createDocument.error ?? deleteDocument.error) as Error
                        ? ((createDocument.error ?? deleteDocument.error) as Error).message
                        : "Request failed"}
                    </p>
                  )}
                </div>

                {activeBaseId && (
                  <div className="border-t pt-4">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      onClick={() => deleteBase.mutate(activeBaseId)}
                    >
                      Delete this base
                    </Button>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Test retrieval</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Input
            value={searchQuery}
            placeholder="What is the cancellation policy?"
            onChange={(event) => setSearchQuery(event.target.value)}
          />
          {search.data && search.data.hits.length > 0 && (
            <ol className="flex flex-col gap-3">
              {search.data.hits.map((hit) => (
                <li key={hit.chunk_id} className="rounded-md border px-3 py-2 text-sm">
                  <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                    <span>{hit.title ?? "Untitled"}</span>
                    <span>score {hit.score.toFixed(3)}</span>
                  </div>
                  <p>{hit.content}</p>
                </li>
              ))}
            </ol>
          )}
          {search.data && searchQuery.trim() && search.data.hits.length === 0 && (
            <p className="text-sm text-muted-foreground">No matching chunks.</p>
          )}
        </CardContent>
      </Card>
    </DashboardLayout>
  );
}