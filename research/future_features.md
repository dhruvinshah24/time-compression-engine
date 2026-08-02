# Future Features (Phase 15+)

As the Time Compression Engine matures, these high-level features represent the long-term vision for the product.

## Multi-Modal Query Language (MMQL)
Allow users to query the compressed database using natural language or structured queries.
*Example: "Show me all sequences where a vehicle arrived but no person exited within 5 minutes."*

## Auto-Generating Textual Incident Reports
Translate the narrative-preserved event graph into a formal, human-readable PDF report suitable for compliance, security handovers, or legal review.

## Synthetic Data Generation Loop
Use the knowledge base and event taxonomy to automatically generate prompts for video synthesis models (like Sora or Gen-3) to create synthetic edge-case data for further training of the Perception Engine.

## Zero-Shot Event Discovery
Move beyond a strict predefined taxonomy and allow the system to cluster and suggest *new* event categories based on recurring unclassified interactions.

## Biometric Integration API
Provide hooks to integrate enterprise access control systems (badge swipes, facial recognition) directly into the event graph to enrich the narrative (e.g., "Person Entered" becomes "Employee John Doe Entered").

## Adaptive Compression Policies
Instead of a fixed target ratio, the policy adapts dynamically based on time of day, facility alert status, or active threat levels (e.g., compress 100:1 normally, but 10:1 during an active alarm).
