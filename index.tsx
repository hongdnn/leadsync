const DIGEST_TRIGGER_URL = process.env.DIGEST_TRIGGER_URL!;
const LEADSYNC_TRIGGER_TOKEN = process.env.LEADSYNC_TRIGGER_TOKEN!;
const WINDOW_MINUTES = Number(process.env.LEADSYNC_DIGEST_WINDOW_MINUTES ?? "60");

function hourBucketStartUtcIso(now = new Date()): string {
  const d = new Date(now);
  d.setUTCMinutes(0, 0, 0);
  return d.toISOString();
}

async function run(): Promise<void> {
  if (!DIGEST_TRIGGER_URL || !LEADSYNC_TRIGGER_TOKEN) {
    throw new Error("Missing DIGEST_TRIGGER_URL or LEADSYNC_TRIGGER_TOKEN");
  }

  const payload = {
    run_source: "scheduled",
    window_minutes: WINDOW_MINUTES,
    bucket_start_utc: hourBucketStartUtcIso(),
  };

  const response = await fetch(DIGEST_TRIGGER_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-LeadSync-Trigger-Token": LEADSYNC_TRIGGER_TOKEN,
    },
    body: JSON.stringify(payload),
  });

  const body = await response.text();
  console.log("Digest trigger response:", response.status, body);

  if (!response.ok) {
    throw new Error(`Digest trigger failed: ${response.status} ${body}`);
  }
}

run()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
