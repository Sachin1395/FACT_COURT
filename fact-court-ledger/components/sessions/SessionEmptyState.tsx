import { FileStack } from "lucide-react";
import { EmptyState } from "../ui/EmptyState";
import { NewSessionButton } from "./NewSessionButton";

export function SessionEmptyState() {
  return (
    <EmptyState
      icon={<FileStack size={26} strokeWidth={1.25} />}
      title="No analysis sessions yet"
      description="Create a session and upload documents to start comparing facts."
      action={<NewSessionButton label="Create Session" />}
    />
  );
}
