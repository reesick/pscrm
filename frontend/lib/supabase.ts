import { createClientComponentClient } from "@supabase/auth-helpers-nextjs";

// Client-side (browser): used in React components for Realtime subscriptions + Auth
export const supabase = createClientComponentClient<any>();
