import { useState } from "react";
import { FilterRow, Segmented } from "./ui/primitives";
import { RankingsView } from "./Rankings";
import { FirstTdAllowedView } from "./FirstTdAllowed";

const VIEWS = ["Player lists", "First TD allowed"] as const;

export function RankingsHub(props: React.ComponentProps<typeof RankingsView>) {
  const [v, setV] = useState<(typeof VIEWS)[number]>("Player lists");
  return (
    <div className="space-y-6">
      <FilterRow label="View"><Segmented label="Rankings view" options={[...VIEWS]} value={v} onChange={setV} /></FilterRow>
      {v === "Player lists" ? <RankingsView {...props} /> : <FirstTdAllowedView />}
    </div>
  );
}
