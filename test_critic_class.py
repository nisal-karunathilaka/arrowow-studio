from app.agents.live_agents import LiveVideoCritic

critic = LiveVideoCritic()
report = critic.generate("output/fbb6e370-c37d-4c65-90ed-16ff93d99d61/veo_final_synced.mp4")
print(f"\nFinal Report JSON: {report}")
