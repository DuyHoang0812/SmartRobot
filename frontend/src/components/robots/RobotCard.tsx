import { Bot } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { UserRobot } from '../../types/robots'
import { RobotStatus } from './RobotStatus'

export function RobotCard({ robot }: { robot: UserRobot }) {
  return <article aria-label={robot.name} className="flex flex-col rounded-xl border border-slate-200 bg-white p-5">
    <div className="mb-5 flex items-start justify-between gap-3">
      <Bot className="shrink-0 text-blue-600" size={25} aria-hidden="true" />
      <RobotStatus status={robot.status} />
    </div>
    <h2 className="mb-6 break-words text-lg font-semibold">{robot.name}</h2>
    <Link to={`/robots/${robot.id}`} className="secondary-button mt-auto text-blue-700"
      aria-label={`Xem xe ${robot.name}`}>Xem xe</Link>
  </article>
}
