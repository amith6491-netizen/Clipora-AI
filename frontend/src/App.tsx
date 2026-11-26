import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { AuthProvider, ProtectedRoute } from "./context/AuthContext";
import { DashboardPage } from "./pages/DashboardPage";
import { DownloadManagerPage } from "./pages/DownloadManagerPage";
import { EditorPage } from "./pages/EditorPage";
import { GalleryPage } from "./pages/GalleryPage";
import { InstagramDownloaderPage } from "./pages/InstagramDownloaderPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { UploadPage } from "./pages/UploadPage";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <AppShell>
                  <DashboardPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/upload"
            element={
              <ProtectedRoute>
                <AppShell>
                  <UploadPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/instagram"
            element={
              <ProtectedRoute>
                <AppShell>
                  <InstagramDownloaderPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/processing"
            element={
              <ProtectedRoute>
                <AppShell>
                  <ProcessingPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/videos/:videoId/processing"
            element={
              <ProtectedRoute>
                <AppShell>
                  <ProcessingPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/gallery"
            element={
              <ProtectedRoute>
                <AppShell>
                  <GalleryPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/videos/:videoId/shorts"
            element={
              <ProtectedRoute>
                <AppShell>
                  <GalleryPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/clips/:clipId/edit"
            element={
              <ProtectedRoute>
                <AppShell>
                  <EditorPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/downloads"
            element={
              <ProtectedRoute>
                <AppShell>
                  <DownloadManagerPage />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
