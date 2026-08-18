import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/** Redirects to /login if not authenticated, or to /home if the route
 * requires SuperAdmin and the current user isn't one — mirrors the
 * Streamlit sidebar only showing SuperAdmin nav items to SuperAdmin. */
export function ProtectedRoute({
  children,
  requireSuperAdmin = false,
}: {
  children: ReactNode;
  requireSuperAdmin?: boolean;
}) {
  const { isAuthenticated, isSuperAdmin } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (requireSuperAdmin && !isSuperAdmin) return <Navigate to="/home" replace />;
  return <>{children}</>;
}
