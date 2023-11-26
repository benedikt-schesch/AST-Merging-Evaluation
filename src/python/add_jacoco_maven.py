# -*- coding: utf-8 -*-
""" Adds Jacoco plugin configuration to a Maven pom.xml file. """

from typing import Any
import argparse
from lxml import etree


def add_jacoco_to_pom(args: Any) -> None:
    """
    Adds Jacoco plugin configuration to a Maven pom.xml file.

    Args:
        args: argparse.Namespace object with 'pom_path' attribute for pom.xml path.
    """
    pom_path = args.pom_path
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(pom_path, parser)
    root = tree.getroot()

    ns = {"mvn": "http://maven.apache.org/POM/4.0.0"}

    build_node = root.find(".//mvn:build", namespaces=ns)
    if build_node is None:
        build_node = etree.SubElement(root, "build")

    plugins_node = build_node.find(".//mvn:plugins", namespaces=ns)
    if plugins_node is None:
        plugins_node = etree.SubElement(build_node, "plugins")

    plugin = etree.SubElement(plugins_node, "plugin")
    etree.SubElement(plugin, "groupId").text = "org.jacoco"
    etree.SubElement(plugin, "artifactId").text = "jacoco-maven-plugin"
    etree.SubElement(plugin, "version").text = "0.8.11"

    executions = etree.SubElement(plugin, "executions")

    execution1 = etree.SubElement(executions, "execution")
    goals1 = etree.SubElement(execution1, "goals")
    etree.SubElement(goals1, "goal").text = "prepare-agent"

    execution2 = etree.SubElement(executions, "execution")
    etree.SubElement(execution2, "id").text = "report"
    etree.SubElement(execution2, "phase").text = "prepare-package"

    goals2 = etree.SubElement(execution2, "goals")
    etree.SubElement(goals2, "goal").text = "report"

    tree.write(pom_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add Jacoco plugin to Maven pom.xml.")
    parser.add_argument("pom_path", type=str, help="Path to the pom.xml file.")

    args = parser.parse_args()
    add_jacoco_to_pom(args)
