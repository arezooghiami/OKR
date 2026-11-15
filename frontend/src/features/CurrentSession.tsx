import { Navigate } from "react-router-dom";
import { useGet } from "../api/typed";
import { Empty, ErrorBox, NoCycle, Skeleton } from "../ui/parts";

/** /session → the open (or latest) session of the user's first visible unit. */
export default function CurrentSession() {
  const { data, error, status, loading, reload } = useGet("/api/v1/dashboard/overview");
  if (loading) return <Skeleton />;
  if (status === 404) return <NoCycle />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const u = data?.units[0];
  const id = u?.current_session_id;
  return id ? <Navigate to={`/sessions/${id}`} replace /> : <Empty title="جلسه‌ای برای شما تعریف نشده است" />;
}
