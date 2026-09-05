import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { ZukanTopPage } from './pages/ZukanTopPage'
import { RegionPage } from './pages/RegionPage'
import { PlayerDetailPage } from './pages/PlayerDetailPage'
import { MyCardEditPage } from './pages/MyCardEditPage'
import { LoginPage } from './pages/LoginPage'
import { OnboardingPage } from './pages/OnboardingPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<ZukanTopPage />} />
        <Route path="/region/:slug" element={<RegionPage />} />
        <Route path="/card/:id" element={<PlayerDetailPage />} />
        <Route path="/me" element={<MyCardEditPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
