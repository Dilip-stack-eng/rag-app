import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ChatProvider } from "./context/ChatContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
import { QueryTracePage } from "./pages/QueryTracePage";
import { KnowledgeBasePage } from "./pages/KnowledgeBasePage";
import { TrainingLogPage } from "./pages/TrainingLogPage";
import { SecurityPage } from "./pages/SecurityPage";
import { QuarantinePage } from "./pages/QuarantinePage";
import { PromptsPage } from "./pages/PromptsPage";
import { UsersPage } from "./pages/UsersPage";
import { ControlPanelPage } from "./pages/ControlPanelPage";

export default function App() {
  return (
    <AuthProvider>
      <ChatProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/home" element={<HomePage />} />
          <Route path="/query-trace" element={<QueryTracePage />} />
          <Route
            path="/knowledge-base"
            element={
              <ProtectedRoute requireSuperAdmin>
                <KnowledgeBasePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/training-log"
            element={
              <ProtectedRoute requireSuperAdmin>
                <TrainingLogPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/security"
            element={
              <ProtectedRoute requireSuperAdmin>
                <SecurityPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/quarantine"
            element={
              <ProtectedRoute requireSuperAdmin>
                <QuarantinePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/prompts"
            element={
              <ProtectedRoute requireSuperAdmin>
                <PromptsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/users"
            element={
              <ProtectedRoute requireSuperAdmin>
                <UsersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/control-panel"
            element={
              <ProtectedRoute requireSuperAdmin>
                <ControlPanelPage />
              </ProtectedRoute>
            }
          />
        </Route>

        <Route path="/" element={<Navigate to="/home" replace />} />
        <Route path="*" element={<Navigate to="/home" replace />} />
      </Routes>
      </ChatProvider>
    </AuthProvider>
  );
}
