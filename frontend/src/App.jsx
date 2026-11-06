import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useParams } from "react-router";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { RequireAnnotator, RequireAuth, RequireRole } from "./components/guards";
import { useAuth } from "./context/auth";
import { CourseDetailPage } from "./pages/admin/CourseDetailPage";
import { CoursesPage } from "./pages/admin/CoursesPage";
import { CycleDetailPage } from "./pages/admin/CycleDetailPage";
import { AdminHome } from "./pages/admin/AdminHome";
import { AnalysisPage } from "./pages/admin/AnalysisPage";
import { CyclesPage } from "./pages/admin/CyclesPage";
import { DepartmentsPage } from "./pages/admin/DepartmentsPage";
import { ModerationPage } from "./pages/admin/ModerationPage";
import { ReportsPage } from "./pages/admin/ReportsPage";
import { UsersPage } from "./pages/admin/UsersPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { LoginPage } from "./pages/LoginPage";
import { CookiesPage, PrivacyPage, TermsPage } from "./pages/legal/LegalPages";
import { MyCoursesPage } from "./pages/MyCoursesPage";
import { ProfileEditorPage } from "./pages/profile/ProfileEditorPage";
import { ProfileReviewPage } from "./pages/profile/ProfileReviewPage";
import { StatusPage } from "./pages/StatusPage";
import { FeedbackFormPage } from "./pages/student/FeedbackFormPage";
import { LabelPage } from "./pages/label/LabelPage";
import { SurveyPage } from "./pages/faculty/SurveyPage";
import { MyFormsPage } from "./pages/student/MyFormsPage";

// The unified page carries Recharts; load it (and the chart library) only when opened.
const InsightsPage = lazy(() =>
  import("./pages/insights/InsightsPage").then((m) => ({ default: m.InsightsPage })),
);
const EvaluationPage = lazy(() =>
  import("./pages/admin/EvaluationPage").then((m) => ({ default: m.EvaluationPage })),
);
const FacultyPage = lazy(() =>
  import("./pages/faculty/FacultyPage").then((m) => ({ default: m.FacultyPage })),
);

/** A new form or person starts with a clean page, so no answers or "thank you" carry over. */
function FeedbackRoute() {
  const { formId } = useParams();
  return <FeedbackFormPage key={formId} />;
}

function FacultyRoute() {
  const { facultyId } = useParams();
  return <FacultyPage key={facultyId ?? "me"} />;
}

function NotFound() {
  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-2">
      <h1 className="m-0 font-marker text-marker">Page not found</h1>
      <p className="m-0 text-muted">This address doesn&apos;t match any FacultyLens screen.</p>
    </div>
  );
}

/** Each role lands on its own first screen. */
function Home() {
  const { user } = useAuth();
  if (user.role === "admin") return <AdminHome />;
  return user.role === "student" ? <MyFormsPage /> : <MyCoursesPage />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/cookies" element={<CookiesPage />} />
        <Route path="/change-password" element={<ChangePasswordPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppShell />}>
            <Route index element={<Home />} />
            <Route element={<RequireRole roles={["student"]} />}>
              <Route path="feedback/:formId" element={<FeedbackRoute />} />
              <Route path="courses" element={<MyCoursesPage />} />
            </Route>
            <Route element={<RequireRole roles={["faculty", "hod"]} />}>
              <Route path="profile" element={<ProfileEditorPage />} />
              <Route path="profile/review" element={<ProfileReviewPage />} />
              <Route path="survey" element={<SurveyPage />} />
              <Route
                path="me"
                element={
                  <Suspense fallback={null}>
                    <FacultyRoute />
                  </Suspense>
                }
              />
            </Route>
            <Route element={<RequireRole roles={["admin", "hod", "faculty"]} />}>
              <Route
                path="faculty/:facultyId"
                element={
                  <Suspense fallback={null}>
                    <FacultyRoute />
                  </Suspense>
                }
              />
            </Route>
            <Route element={<RequireRole roles={["admin", "hod"]} />}>
              <Route
                path="insights"
                element={
                  <Suspense fallback={null}>
                    <InsightsPage />
                  </Suspense>
                }
              />
            </Route>
            <Route path="label" element={<RequireAnnotator />}>
              <Route index element={<LabelPage />} />
            </Route>
            <Route path="admin" element={<RequireRole roles={["admin"]} />}>
              <Route index element={<Navigate to="users" replace />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="departments" element={<DepartmentsPage />} />
              <Route path="courses" element={<CoursesPage />} />
              <Route path="courses/:courseId" element={<CourseDetailPage />} />
              <Route path="faculty/:facultyId/profile" element={<ProfileEditorPage />} />
              <Route path="faculty/:facultyId/profile/review" element={<ProfileReviewPage />} />
              <Route path="cycles" element={<CyclesPage />} />
              <Route path="cycles/:cycleId" element={<CycleDetailPage />} />
              <Route path="analysis" element={<AnalysisPage />} />
              <Route path="moderation" element={<ModerationPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="status" element={<StatusPage />} />
              <Route
                path="evaluation"
                element={
                  <Suspense fallback={null}>
                    <EvaluationPage />
                  </Suspense>
                }
              />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Route>
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
