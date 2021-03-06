

Feature: Publish model asset from Maya

	Background:
		Given an environment that meets the Avalon's demand
		And I initiate Avalon

    Scenario: model mesh is triangulate
        Given a model which has triangulated faces
        When the artist want to publish it
        Then Pyblish will block with quadrangular validation fail

    Scenario: model has multiple shapes
        Given a model which has multiple shape nodes
        When the artist want to publish it
        Then Pyblish will block with single shape validation fail
