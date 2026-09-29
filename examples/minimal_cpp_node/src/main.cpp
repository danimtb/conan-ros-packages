#include <memory>

#include <geometry_msgs/msg/twist.hpp>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("minimal_cpp_node");

  auto status = node->create_publisher<std_msgs::msg::String>("status", 10);
  auto cmd_vel = node->create_subscription<geometry_msgs::msg::Twist>(
    "cmd_vel", 10, [](geometry_msgs::msg::Twist::SharedPtr) {});

  std_msgs::msg::String message;
  message.data = "ready";
  status->publish(message);
  RCLCPP_INFO(
    node->get_logger(),
    "minimal C++ node: publishing %s, subscribing %s",
    status->get_topic_name(), cmd_vel->get_topic_name());

  rclcpp::shutdown();
  return 0;
}
