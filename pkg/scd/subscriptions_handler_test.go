package scd

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/interuss/dss/pkg/api"
	restapi "github.com/interuss/dss/pkg/api/scdv1"
	"github.com/interuss/dss/pkg/memstore"
	"github.com/interuss/dss/pkg/scd/models"
	"github.com/interuss/dss/pkg/scd/operations"
	"github.com/interuss/dss/pkg/scd/repos"
	scdmemstore "github.com/interuss/dss/pkg/scd/store/memstore"
	dssstore "github.com/interuss/dss/pkg/store"
	"github.com/interuss/dss/pkg/timestamp"
	"github.com/interuss/stacktrace"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

type testStore struct {
	*memstore.Store[repos.Repository]
}

func (s *testStore) Transact(ctx context.Context, req dssstore.OperationRequest) (any, error) {
	handler, ok := operations.Registry[req.OperationID()]
	if !ok {
		return nil, stacktrace.NewError("unknown operation %q", req.OperationID())
	}
	return handler.Execute(ctx, s.GetRepo(), req)
}

func newTestServer(t *testing.T) (*Server, context.Context) {
	t.Helper()
	now := time.Date(2026, time.October, 1, 12, 0, 0, 0, time.UTC)
	ctx := timestamp.NewContext(context.Background(), now)
	ms, err := scdmemstore.Init(ctx, zap.NewNop())
	require.NoError(t, err)
	ms.Restore()
	return &Server{
		Store:             &testStore{Store: ms},
		AllowHTTPBaseUrls: true,
	}, ctx
}

func testVolume4D(now time.Time) restapi.Volume4D {
	startStr := now.Format(time.RFC3339)
	endStr := now.Add(25 * time.Minute).Format(time.RFC3339)
	return restapi.Volume4D{
		TimeStart: &restapi.Time{Value: startStr, Format: models.TimeFormatRFC3339},
		TimeEnd:   &restapi.Time{Value: endStr, Format: models.TimeFormatRFC3339},
		Volume: restapi.Volume3D{
			OutlineCircle: &restapi.Circle{
				Center: &restapi.LatLngPoint{Lat: 37.427636, Lng: -122.170502},
				Radius: &restapi.Radius{Value: 900, Units: "M"},
			},
			AltitudeLower: &restapi.Altitude{Value: 0, Reference: models.ReferenceW84, Units: models.UnitsM},
			AltitudeUpper: &restapi.Altitude{Value: 300, Reference: models.ReferenceW84, Units: models.UnitsM},
		},
	}
}

func seedEntities(t *testing.T, srv *Server, ctx context.Context, vol restapi.Volume4D) (restapi.EntityID, restapi.EntityOVN, restapi.EntityID) {
	t.Helper()
	oiManager := "oi_manager"
	constraintManager := "constraint_manager"

	oiSubIDStr := uuid.NewString()
	oiSubID := restapi.SubscriptionID(oiSubIDStr)
	oiSubEntityID := restapi.EntityID(oiSubIDStr)
	notifyOI := true
	notifyCon := false
	subResp := srv.CreateSubscription(ctx, &restapi.CreateSubscriptionRequest{
		Subscriptionid: oiSubID,
		Auth: api.AuthorizationResult{
			ClientID: &oiManager,
			Scopes:   []string{string(restapi.UtmStrategicCoordinationScope)},
		},
		Body: &restapi.PutSubscriptionParameters{
			Extents:                     vol,
			UssBaseUrl:                  "https://oi-manager.example.com/uss",
			NotifyForOperationalIntents: &notifyOI,
			NotifyForConstraints:        &notifyCon,
		},
	})
	require.NotNil(t, subResp.Response200)

	oiID := restapi.EntityID(uuid.NewString())
	oiResp := srv.CreateOperationalIntentReference(ctx, &restapi.CreateOperationalIntentReferenceRequest{
		Entityid: oiID,
		Auth: api.AuthorizationResult{
			ClientID: &oiManager,
			Scopes:   []string{string(restapi.UtmStrategicCoordinationScope)},
		},
		Body: &restapi.PutOperationalIntentReferenceParameters{
			Extents:        []restapi.Volume4D{vol},
			State:          restapi.OperationalIntentState_Accepted,
			UssBaseUrl:     "https://oi-manager.example.com/uss",
			SubscriptionId: &oiSubEntityID,
		},
	})
	require.NotNil(t, oiResp.Response201)
	require.NotNil(t, oiResp.Response201.OperationalIntentReference.Ovn)
	oiOVN := *oiResp.Response201.OperationalIntentReference.Ovn

	constraintID := restapi.EntityID(uuid.NewString())
	conResp := srv.CreateConstraintReference(ctx, &restapi.CreateConstraintReferenceRequest{
		Entityid: constraintID,
		Auth: api.AuthorizationResult{
			ClientID: &constraintManager,
			Scopes:   []string{string(restapi.UtmConstraintManagementScope)},
		},
		Body: &restapi.PutConstraintReferenceParameters{
			Extents:    []restapi.Volume4D{vol},
			UssBaseUrl: "https://constraint-manager.example.com/uss",
		},
	})
	require.NotNil(t, conResp.Response201)

	return oiID, oiOVN, constraintID
}

// This test is AI-generated and has not been closely inspected by a human.
func TestCreateSubscriptionScopeGating(t *testing.T) {
	strategicOnly := []string{string(restapi.UtmStrategicCoordinationScope)}
	constraintOnly := []string{string(restapi.UtmConstraintProcessingScope)}
	bothScopes := []string{
		string(restapi.UtmStrategicCoordinationScope),
		string(restapi.UtmConstraintProcessingScope),
	}

	testCases := []struct {
		name              string
		scopes            []string
		notifyOpIntents   bool
		notifyConstraints bool
		want403           bool
		wantOIRefs        bool
		wantConRefs       bool
	}{
		{
			name:              "strategic_only_operational_intents_only",
			scopes:            strategicOnly,
			notifyOpIntents:   true,
			notifyConstraints: false,
			want403:           false,
			wantOIRefs:        true,
			wantConRefs:       false,
		},
		{
			name:              "constraint_only_constraints_only",
			scopes:            constraintOnly,
			notifyOpIntents:   false,
			notifyConstraints: true,
			want403:           false,
			wantOIRefs:        false,
			wantConRefs:       true,
		},
		{
			name:              "both_scopes_both_classes",
			scopes:            bothScopes,
			notifyOpIntents:   true,
			notifyConstraints: true,
			want403:           false,
			wantOIRefs:        true,
			wantConRefs:       true,
		},
		{
			name:              "strategic_only_constraints_only",
			scopes:            strategicOnly,
			notifyOpIntents:   false,
			notifyConstraints: true,
			want403:           true,
		},
		{
			name:              "constraint_only_operational_intents_only",
			scopes:            constraintOnly,
			notifyOpIntents:   true,
			notifyConstraints: false,
			want403:           true,
		},
		{
			name:              "strategic_only_both_classes",
			scopes:            strategicOnly,
			notifyOpIntents:   true,
			notifyConstraints: true,
			want403:           true,
		},
		{
			name:              "constraint_only_both_classes",
			scopes:            constraintOnly,
			notifyOpIntents:   true,
			notifyConstraints: true,
			want403:           true,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			srv, ctx := newTestServer(t)
			vol := testVolume4D(timestamp.MustFromContext(ctx))
			oiID, _, conID := seedEntities(t, srv, ctx, vol)

			subscriber := "subscriber_client"
			subID := restapi.SubscriptionID(uuid.NewString())
			notifyOI := tc.notifyOpIntents
			notifyCon := tc.notifyConstraints

			resp := srv.CreateSubscription(ctx, &restapi.CreateSubscriptionRequest{
				Subscriptionid: subID,
				Auth: api.AuthorizationResult{
					ClientID: &subscriber,
					Scopes:   tc.scopes,
				},
				Body: &restapi.PutSubscriptionParameters{
					Extents:                     vol,
					UssBaseUrl:                  "https://subscriber.example.com/uss",
					NotifyForOperationalIntents: &notifyOI,
					NotifyForConstraints:        &notifyCon,
				},
			})

			if tc.want403 {
				require.NotNil(t, resp.Response403)
				require.Nil(t, resp.Response200)

				// Ensure rejected subscription was not persisted.
				getResp := srv.GetSubscription(ctx, &restapi.GetSubscriptionRequest{
					Subscriptionid: subID,
					Auth: api.AuthorizationResult{
						ClientID: &subscriber,
						Scopes:   bothScopes,
					},
				})
				require.NotNil(t, getResp.Response404)
				return
			}

			require.NotNil(t, resp.Response200)
			require.Nil(t, resp.Response403)

			if tc.wantOIRefs {
				require.NotNil(t, resp.Response200.OperationalIntentReferences)
				require.Len(t, *resp.Response200.OperationalIntentReferences, 1)
				require.Equal(t, oiID, (*resp.Response200.OperationalIntentReferences)[0].Id)
			} else {
				require.Nil(t, resp.Response200.OperationalIntentReferences)
			}

			if tc.wantConRefs {
				require.NotNil(t, resp.Response200.ConstraintReferences)
				require.Len(t, *resp.Response200.ConstraintReferences, 1)
				require.Equal(t, conID, (*resp.Response200.ConstraintReferences)[0].Id)
			} else {
				require.Nil(t, resp.Response200.ConstraintReferences)
			}
		})
	}
}

// This test is AI-generated and has not been closely inspected by a human.
func TestUpdateSubscriptionScopeGatingAndNotifications(t *testing.T) {
	strategicOnly := []string{string(restapi.UtmStrategicCoordinationScope)}
	constraintOnly := []string{string(restapi.UtmConstraintProcessingScope)}
	bothScopes := []string{
		string(restapi.UtmStrategicCoordinationScope),
		string(restapi.UtmConstraintProcessingScope),
	}

	t.Run("strategic_only_cannot_broaden_to_constraints", func(t *testing.T) {
		srv, ctx := newTestServer(t)
		vol := testVolume4D(timestamp.MustFromContext(ctx))
		_, _, _ = seedEntities(t, srv, ctx, vol)

		subscriber := "strategic_subscriber"
		subID := restapi.SubscriptionID(uuid.NewString())
		tTrue := true
		tFalse := false

		// Create valid strategic-only subscription.
		createResp := srv.CreateSubscription(ctx, &restapi.CreateSubscriptionRequest{
			Subscriptionid: subID,
			Auth: api.AuthorizationResult{
				ClientID: &subscriber,
				Scopes:   strategicOnly,
			},
			Body: &restapi.PutSubscriptionParameters{
				Extents:                     vol,
				UssBaseUrl:                  "https://strategic-sub.example.com/uss",
				NotifyForOperationalIntents: &tTrue,
				NotifyForConstraints:        &tFalse,
			},
		})
		require.NotNil(t, createResp.Response200)
		version := string(createResp.Response200.Subscription.Version)

		// Attempt to update to notify_for_constraints=true with only strategic scope.
		updateResp := srv.UpdateSubscription(ctx, &restapi.UpdateSubscriptionRequest{
			Subscriptionid: subID,
			Version:        version,
			Auth: api.AuthorizationResult{
				ClientID: &subscriber,
				Scopes:   strategicOnly,
			},
			Body: &restapi.PutSubscriptionParameters{
				Extents:                     vol,
				UssBaseUrl:                  "https://strategic-sub.example.com/uss",
				NotifyForOperationalIntents: &tFalse,
				NotifyForConstraints:        &tTrue,
			},
		})
		require.NotNil(t, updateResp.Response403)
		require.Nil(t, updateResp.Response200)

		// Create a new Constraint and verify the subscriber is NOT in SubscribersToNotify.
		constraintManager := "constraint_manager"
		newConResp := srv.CreateConstraintReference(ctx, &restapi.CreateConstraintReferenceRequest{
			Entityid: restapi.EntityID(uuid.NewString()),
			Auth: api.AuthorizationResult{
				ClientID: &constraintManager,
				Scopes:   []string{string(restapi.UtmConstraintManagementScope)},
			},
			Body: &restapi.PutConstraintReferenceParameters{
				Extents:    []restapi.Volume4D{vol},
				UssBaseUrl: "https://constraint-manager.example.com/uss",
			},
		})
		require.NotNil(t, newConResp.Response201)
		for _, subToNotify := range newConResp.Response201.Subscribers {
			for _, subRef := range subToNotify.Subscriptions {
				require.NotEqual(t, subID, subRef.SubscriptionId)
			}
		}

		// Updating with dual scopes succeeds.
		dualUpdateResp := srv.UpdateSubscription(ctx, &restapi.UpdateSubscriptionRequest{
			Subscriptionid: subID,
			Version:        version,
			Auth: api.AuthorizationResult{
				ClientID: &subscriber,
				Scopes:   bothScopes,
			},
			Body: &restapi.PutSubscriptionParameters{
				Extents:                     vol,
				UssBaseUrl:                  "https://strategic-sub.example.com/uss",
				NotifyForOperationalIntents: &tTrue,
				NotifyForConstraints:        &tTrue,
			},
		})
		require.NotNil(t, dualUpdateResp.Response200)
		require.NotNil(t, dualUpdateResp.Response200.ConstraintReferences)
	})

	t.Run("constraint_only_cannot_broaden_to_operational_intents", func(t *testing.T) {
		srv, ctx := newTestServer(t)
		vol := testVolume4D(timestamp.MustFromContext(ctx))
		_, oiOVN, _ := seedEntities(t, srv, ctx, vol)

		subscriber := "constraint_subscriber"
		subID := restapi.SubscriptionID(uuid.NewString())
		tTrue := true
		tFalse := false

		// Create valid constraint-only subscription.
		createResp := srv.CreateSubscription(ctx, &restapi.CreateSubscriptionRequest{
			Subscriptionid: subID,
			Auth: api.AuthorizationResult{
				ClientID: &subscriber,
				Scopes:   constraintOnly,
			},
			Body: &restapi.PutSubscriptionParameters{
				Extents:                     vol,
				UssBaseUrl:                  "https://constraint-sub.example.com/uss",
				NotifyForOperationalIntents: &tFalse,
				NotifyForConstraints:        &tTrue,
			},
		})
		require.NotNil(t, createResp.Response200)
		version := string(createResp.Response200.Subscription.Version)

		// Attempt to update to notify_for_operational_intents=true with only constraint scope.
		updateResp := srv.UpdateSubscription(ctx, &restapi.UpdateSubscriptionRequest{
			Subscriptionid: subID,
			Version:        version,
			Auth: api.AuthorizationResult{
				ClientID: &subscriber,
				Scopes:   constraintOnly,
			},
			Body: &restapi.PutSubscriptionParameters{
				Extents:                     vol,
				UssBaseUrl:                  "https://constraint-sub.example.com/uss",
				NotifyForOperationalIntents: &tTrue,
				NotifyForConstraints:        &tFalse,
			},
		})
		require.NotNil(t, updateResp.Response403)
		require.Nil(t, updateResp.Response200)

		// Create a new Operational Intent and verify the subscriber is NOT in SubscribersToNotify.
		oiManager := "oi_manager_2"
		oiSubIDStr := uuid.NewString()
		oiSubID := restapi.SubscriptionID(oiSubIDStr)
		oiSubEntityID := restapi.EntityID(oiSubIDStr)
		oiSubResp := srv.CreateSubscription(ctx, &restapi.CreateSubscriptionRequest{
			Subscriptionid: oiSubID,
			Auth: api.AuthorizationResult{
				ClientID: &oiManager,
				Scopes:   strategicOnly,
			},
			Body: &restapi.PutSubscriptionParameters{
				Extents:                     vol,
				UssBaseUrl:                  "https://oi-manager-2.example.com/uss",
				NotifyForOperationalIntents: &tTrue,
				NotifyForConstraints:        &tFalse,
			},
		})
		require.NotNil(t, oiSubResp.Response200)

		key := restapi.Key{oiOVN}
		newOIResp := srv.CreateOperationalIntentReference(ctx, &restapi.CreateOperationalIntentReferenceRequest{
			Entityid: restapi.EntityID(uuid.NewString()),
			Auth: api.AuthorizationResult{
				ClientID: &oiManager,
				Scopes:   strategicOnly,
			},
			Body: &restapi.PutOperationalIntentReferenceParameters{
				Extents:        []restapi.Volume4D{vol},
				State:          restapi.OperationalIntentState_Accepted,
				UssBaseUrl:     "https://oi-manager-2.example.com/uss",
				SubscriptionId: &oiSubEntityID,
				Key:            &key,
			},
		})
		require.NotNil(t, newOIResp.Response201)
		for _, subToNotify := range newOIResp.Response201.Subscribers {
			for _, subRef := range subToNotify.Subscriptions {
				require.NotEqual(t, subID, subRef.SubscriptionId)
			}
		}
	})
}
