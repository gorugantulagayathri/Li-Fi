"""
Predefined Demonstration Scenarios for Hackathon Presentation.
"""

from typing import Dict, Any, List
from environment import Environment, AccessPoint, Obstacle
from users import User, UserManager

class ScenarioEngine:
    @staticmethod
    def setup_scenario(scenario_name: str, env: Environment, user_mgr: UserManager):
        env.aps.clear()
        env.obstacles.clear()
        user_mgr.users.clear()

        width = env.width
        height = env.height

        if scenario_name == "Walking Through Beam":
            # MAIN DEMO SCENARIO
            # 2 APs, 1 Obstacle in middle, User 1 walks directly past obstacle crossing AP1 line-of-sight
            env.add_ap(AccessPoint("AP1", x=4.0, y=6.0))
            env.add_ap(AccessPoint("AP2", x=16.0, y=6.0))

            # Obstacle blocking AP1 path when user reaches x ~ 8-10
            env.add_obstacle(Obstacle("OBS1", "Partition Wall", x=8.0, y=3.5, width=1.5, height=5.0))

            # User 1 starts left, moves straight right towards x=18.0
            u1 = User(
                id="U1",
                x=2.0,
                y=6.0,
                speed=1.2,
                movement_mode="Directed",
                target_waypoint=(18.0, 6.0),
                priority=3
            )
            user_mgr.add_user(u1)

            # User 2 & 3 stationary background users
            user_mgr.add_user(User("U2", x=4.0, y=3.0, speed=0.5, movement_mode="Random Walk"))
            user_mgr.add_user(User("U3", x=16.0, y=9.0, speed=0.5, movement_mode="Random Walk"))

        elif scenario_name == "High Density":
            # 4 APs, 18 users, AP load balancing demonstration
            ap_coords = [(4.0, 3.5), (16.0, 3.5), (4.0, 8.5), (16.0, 8.5)]
            for i, (x, y) in enumerate(ap_coords):
                env.add_ap(AccessPoint(f"AP{i+1}", x=x, y=y, max_capacity=5))

            env.add_obstacle(Obstacle("OBS1", "Bookshelf", x=7.5, y=3.0, width=1.2, height=4.5))
            env.add_obstacle(Obstacle("OBS2", "Meeting Pod", x=12.0, y=5.0, width=2.5, height=2.5))

            user_mgr.create_default_users(num_users=18, room_width=width, room_height=height)

        elif scenario_name == "Multiple Blockages":
            # 3 APs, 8 users, 4 obstacles
            env.add_ap(AccessPoint("AP1", x=5.0, y=6.0))
            env.add_ap(AccessPoint("AP2", x=10.0, y=6.0))
            env.add_ap(AccessPoint("AP3", x=15.0, y=6.0))

            env.add_obstacle(Obstacle("OBS1", "Partition A", x=7.0, y=2.0, width=1.0, height=4.0))
            env.add_obstacle(Obstacle("OBS2", "Partition B", x=12.0, y=6.0, width=1.0, height=4.0))
            env.add_obstacle(Obstacle("OBS3", "Storage Unit", x=4.0, y=8.0, width=3.0, height=1.5))
            env.add_obstacle(Obstacle("OBS4", "Pillar", x=14.0, y=2.0, width=1.5, height=1.5))

            user_mgr.create_default_users(num_users=8, room_width=width, room_height=height)

        else:  # "Free Movement" (Default)
            env.aps.clear()
            default_env = Environment.create_default(num_aps=3, num_obstacles=3, width=width, height=height)
            env.aps = default_env.aps
            env.obstacles = default_env.obstacles
            user_mgr.create_default_users(num_users=6, room_width=width, room_height=height)
