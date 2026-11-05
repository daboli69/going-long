import { useState } from "react";
import { FilterRow, Segmented } from "./ui/primitives";
import { RankingsView } from "./Rankings";
import { FirstTdAllowedView } from "./FirstTdAllowed";
import { OverUnderCallsView } from "./OverUnderCalls";

const VIEWS = ["Player lists", "First TD allowed", "Over/under calls"] as const;

export function RankingsHub(props: React.ComponentProps<typeof RankingsView>) {
  const [v, setV] = useState<(typeof VIEWS)[number]>("Player lists");
  return (
    <div className="space-y-6">
      <FilterRow label="View"><Segmented label="Rankings view" options={[...VIEWS]} value={v} onChange={setV} /></FilterRow>
      {v === "Player lists" ? <RankingsView {...props} /> : v === "First TD allowed" ? <FirstTdAllowedView /> : <OverUnderCallsView />}
    </div>
  );
}
