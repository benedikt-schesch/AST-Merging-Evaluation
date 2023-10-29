""" Adds Jacoco plugin configuration to a Gradle build file. """


def update_gradle_for_jacoco(gradle_path: str) -> None:
    """
    Updates a Gradle build file to include Jacoco configurations.

    Args:
        gradle_path: Path to the build.gradle file.
    """
    jacoco_config = "\napply plugin: 'jacoco'\n"
    jacoco_report_config = (
        "jacocoTestReport {\n    reports {\n        xml.enabled true\n"
        + "        html.enabled true\n    }\n}"
    )

    with open(gradle_path, "r+") as f:
        content = f.read()

        # Only add Jacoco plugin if it's not already there
        if "apply plugin: 'jacoco'" not in content:
            f.write(jacoco_config)

        # Only add Jacoco report config if it's not already there
        if "jacocoTestReport {" not in content:
            f.write(jacoco_report_config)


if __name__ == "__main__":
    gradle_path = "path/to/your/build.gradle"
    update_gradle_for_jacoco(gradle_path)
