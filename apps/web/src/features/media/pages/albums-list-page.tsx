import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAlbumsList } from "@/features/media/api/media-hooks";
import { AlbumFormDialog } from "@/features/media/components/album-form-dialog";

const PAGE_SIZE = 20;

export function AlbumsListPage() {
  const navigate = useNavigate();
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useAlbumsList({ skip, limit: PAGE_SIZE });

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Media Gallery</h1>
          <p className="mt-1 text-muted-foreground">
            Photo and file albums for events, workshops, and campus life.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Album
        </Button>
      </div>

      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <p className="py-8 text-center text-sm text-destructive">
          Failed to load albums. Please try again.
        </p>
      )}

      {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No albums found. Create your first album to get started.
        </p>
      )}

      {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data?.items.map((album) => (
            <Card
              key={album.id}
              className="cursor-pointer transition-colors hover:bg-accent/50"
              onClick={() => navigate(`/media/albums/${album.id}`)}
            >
              <CardHeader>
                <CardTitle className="text-base">{album.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="line-clamp-2 text-sm text-muted-foreground">
                  {album.description || "No description."}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {!isLoading && total > PAGE_SIZE && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-sm text-muted-foreground">
            Page {page} of {pageCount} ({total} albums)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={skip === 0}
              onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={skip + PAGE_SIZE >= total}
              onClick={() => setSkip(skip + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      <AlbumFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
