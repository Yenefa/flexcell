"""One isolated, bounded Gazebo set_pose RPC; no native Python callbacks."""
import argparse
import json
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('xyz', nargs=3, type=float)
    args = ap.parse_args()
    from gz.msgs10 import boolean_pb2, pose_pb2
    from gz.transport13 import Node
    node = Node()
    req = pose_pb2.Pose()
    req.name = args.name
    req.position.x, req.position.y, req.position.z = args.xyz
    req.orientation.w = 1.
    started = time.monotonic()
    ok, response = node.request('/world/empty/set_pose', req, pose_pb2.Pose,
                                boolean_pb2.Boolean, 1000)
    print(json.dumps(dict(transport_ok=bool(ok), response_data=bool(response.data),
                          elapsed_s=time.monotonic() - started)), flush=True)


if __name__ == '__main__':
    main()
