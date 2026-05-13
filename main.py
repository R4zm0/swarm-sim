from core.world import World

def main():
    world = World()
    world.add_drone("fpv")
    world.add_drone("mavic_isr")
    world.add_drone("lancet")

    for drone_id, drone in world.drones.items():
        print(f"[{drone_id}] : speed: {drone.effective_speed}")

if __name__ == "__main__":
    main()
