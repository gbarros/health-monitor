"use client";

import { type FC, useEffect, useRef, useState } from "react";
import {
  XIcon,
  PlusIcon,
  FileText,
  ImageIcon,
  Loader2Icon,
  AlertCircleIcon,
} from "lucide-react";
import {
  AttachmentPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  useAuiState,
  useAui,
  useComposerRuntime,
} from "@assistant-ui/react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { cn } from "@/lib/utils";
import { recordClientEvent, telemetryOperationId } from "@/clientTelemetry";

const AttachmentThumb: FC = () => {
  const isImage = useAuiState((s) => s.attachment.type === "image");
  const file = useAuiState((s) => s.attachment.file);
  const [thumbnail, setThumbnail] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setThumbnail(null);
    if (!isImage || !file || typeof createImageBitmap !== "function") return;

    void createImageBitmap(file, {
      resizeWidth: 192,
      resizeHeight: 192,
      resizeQuality: "low",
    })
      .then((bitmap) => {
        const canvas = document.createElement("canvas");
        canvas.width = 128;
        canvas.height = 128;
        canvas.getContext("2d")?.drawImage(bitmap, 0, 0, 128, 128);
        bitmap.close();
        if (!cancelled) setThumbnail(canvas.toDataURL("image/jpeg", 0.72));
      })
      .catch(() => {
        // Keep the lightweight icon when this browser cannot decode safely.
      });

    return () => {
      cancelled = true;
    };
  }, [file, isImage]);

  return (
    <div className="flex h-full w-full items-center justify-center">
      {isImage && thumbnail ? (
        <img
          src={thumbnail}
          alt=""
          aria-hidden="true"
          className="size-full object-cover"
          width={128}
          height={128}
        />
      ) : isImage ? (
        <ImageIcon className="aui-attachment-tile-image-icon text-muted-foreground size-7" />
      ) : (
        <FileText className="aui-attachment-tile-fallback-icon text-muted-foreground size-7" />
      )}
    </div>
  );
};

const AttachmentUI: FC = () => {
  const aui = useAui();
  const isComposer = aui.attachment.source !== "message";

  const isImage = useAuiState((s) => s.attachment.type === "image");
  const typeLabel = useAuiState((s) => {
    const type = s.attachment.type;
    switch (type) {
      case "image":
        return "Image";
      case "document":
        return "Document";
      case "file":
        return "File";
      default:
        return type;
    }
  });

  const uploadState = useAuiState((s) =>
    s.attachment.status.type === "running"
      ? "uploading"
      : s.attachment.status.type === "incomplete" &&
          s.attachment.status.reason === "error"
        ? "error"
        : undefined,
  );
  const isUploading = uploadState === "uploading";
  const isError = uploadState === "error";

  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <AttachmentPrimitive.Root
          className={cn(
            "aui-attachment-root relative",
            isImage &&
              !isComposer &&
              "aui-attachment-root-message only:*:first:size-24",
          )}
        >
          <TooltipTrigger asChild>
            <div
              className={cn(
                "aui-attachment-tile bg-muted relative size-14 overflow-hidden rounded-[calc(var(--composer-radius)-var(--composer-padding))] border",
                isError && "border-destructive",
              )}
              role="img"
              tabIndex={0}
              aria-label={`${typeLabel} attachment${
                isError ? ", upload failed" : isUploading ? ", uploading" : ""
              }`}
            >
              <AttachmentThumb />
              {isUploading && (
                <div
                  aria-hidden="true"
                  className="aui-attachment-tile-uploading bg-background/60 absolute inset-0 flex items-center justify-center backdrop-blur-[1px]"
                >
                  <Loader2Icon className="text-muted-foreground size-5 animate-spin" />
                </div>
              )}
              {isError && (
                <div
                  aria-hidden="true"
                  className="aui-attachment-tile-error bg-destructive/10 absolute inset-0 flex items-center justify-center"
                >
                  <AlertCircleIcon className="text-destructive size-5" />
                </div>
              )}
            </div>
          </TooltipTrigger>
          {isComposer && <AttachmentRemove />}
        </AttachmentPrimitive.Root>
        <TooltipContent side="top">
          <AttachmentPrimitive.Name />
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

const AttachmentRemove: FC = () => {
  return (
    <AttachmentPrimitive.Remove asChild>
      <TooltipIconButton
        tooltip="Remover anexo"
        className="aui-attachment-tile-remove text-muted-foreground hover:[&_svg]:text-destructive absolute end-1.5 top-1.5 size-3.5 rounded-full bg-white opacity-100 shadow-sm hover:bg-white! [&_svg]:text-black"
        side="top"
      >
        <XIcon className="aui-attachment-remove-icon size-3 dark:stroke-[2.5px]" />
      </TooltipIconButton>
    </AttachmentPrimitive.Remove>
  );
};

export const UserMessageAttachments: FC = () => {
  return (
    <div className="aui-user-message-attachments-end col-span-full col-start-1 row-start-1 flex w-full flex-row justify-end gap-2">
      <MessagePrimitive.Attachments>
        {() => <AttachmentUI />}
      </MessagePrimitive.Attachments>
    </div>
  );
};

export const ComposerAttachments: FC = () => {
  return (
    <div className="aui-composer-attachments flex w-full flex-row items-center gap-2 overflow-x-auto empty:hidden">
      <ComposerPrimitive.Attachments>
        {() => <AttachmentUI />}
      </ComposerPrimitive.Attachments>
    </div>
  );
};

export const ComposerAddAttachment: FC = () => {
  const composer = useComposerRuntime();
  const attachmentAccept = composer.getState().attachmentAccept;
  const operationRef = useRef<string | null>(null);

  return (
    <div className="aui-composer-add-attachment hover:bg-muted-foreground/15 dark:border-muted-foreground/15 dark:hover:bg-muted-foreground/30 focus-within:ring-ring/50 relative size-11 overflow-hidden rounded-full text-xs font-semibold focus-within:ring-[3px]">
      <PlusIcon
        className="aui-attachment-add-icon pointer-events-none absolute left-1/2 top-1/2 size-4.5 -translate-x-1/2 -translate-y-1/2 stroke-[1.5px]"
        aria-hidden="true"
      />
      <input
        type="file"
        accept={attachmentAccept === "*" ? undefined : attachmentAccept}
        multiple
        className="absolute inset-0 size-full cursor-pointer opacity-0"
        aria-label="Anexar foto ou arquivo"
        onClick={() => {
          const operationId = telemetryOperationId("picker");
          operationRef.current = operationId;
          recordClientEvent("client.attachment.picker_opened", {
            operation_id: operationId,
            accept_types: attachmentAccept,
            allows_multiple: true,
          });
        }}
        onChange={(event) => {
          const files = Array.from(event.currentTarget.files ?? []);
          event.currentTarget.value = "";
          const operationId = operationRef.current ?? telemetryOperationId("picker");
          operationRef.current = null;
          recordClientEvent("client.attachment.selection_returned", {
            operation_id: operationId,
            file_count: files.length,
            total_bytes: files.reduce((total, file) => total + file.size, 0),
            max_bytes: files.reduce((maximum, file) => Math.max(maximum, file.size), 0),
            mime_types: Array.from(new Set(files.map((file) => file.type || "unknown"))),
          });
          void Promise.all(files.map((file) => composer.addAttachment(file)))
            .then(() => {
              recordClientEvent("client.attachment.composer_add_completed", {
                operation_id: operationId,
                file_count: files.length,
              });
            })
            .catch((error) => {
              recordClientEvent(
                "client.attachment.composer_add_failed",
                {
                  operation_id: operationId,
                  error_name: error instanceof Error ? error.name : typeof error,
                  error_detail: error instanceof Error ? error.message.slice(0, 300) : String(error).slice(0, 300),
                },
                "error",
              );
            });
        }}
      />
    </div>
  );
};
